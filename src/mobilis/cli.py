"""Commande `mobilis` : reproduit les chiffres du dossier à partir des fichiers bruts."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
import tracemalloc
from collections.abc import Sequence
from decimal import Decimal
from enum import Enum
from pathlib import Path

from mobilis.abonnes import ECARTEES_ABONNES, AnomalieAbonne, Formule, lire_abonnes
from mobilis.bornes import (
    ClientBornes,
    ClientBornesAsync,
    ErreurApi,
    Photo,
    comparer,
    photographier_asyncio,
    photographier_sequentiel,
    photographier_threads,
)
from mobilis.facturation import AnomalieFacturation, Facturation, facturer_fichier, lire_tarifs
from mobilis.journal import Journal
from mobilis.stations import CORRIGEABLES, RapportStations, lire_stations
from mobilis.trajets import (
    ECARTEES,
    Frequentation,
    TypeJour,
    analyser_trajets,
    stations_qui_se_vident,
)

DONNEES_PAR_DEFAUT = Path("kit/donnees")
URL_API_PAR_DEFAUT = "http://127.0.0.1:8765"
FICHIER_TRAJETS = "trajets_2026-08_2026-10.csv.gz"
FICHIER_ABONNES = "abonnes.jsonl"
FICHIER_TARIFS = "tarifs.json"

DECISIONS: dict[Enum, str] = {
    **dict.fromkeys(ECARTEES | ECARTEES_ABONNES, "écartée"),
    AnomalieAbonne.FORMULE_NORMALISEE: "corrigée",
    AnomalieAbonne.TRONQUEE_RECUPEREE: "corrigée",
    AnomalieFacturation.ABONNE_INTROUVABLE: "occasionnel, signalé",
    AnomalieFacturation.ABONNEMENT_INACTIF: "occasionnel",
    AnomalieFacturation.FANTOME: "non facturé, signalé",
    AnomalieFacturation.NON_RESTITUTION: "pénalité",
}


def dossier_donnees(option: str | None) -> Path:
    """Priorité : option --donnees, puis MOBILIS_DONNEES, puis kit/donnees."""
    if option:
        return Path(option)
    return Path(os.environ.get("MOBILIS_DONNEES", DONNEES_PAR_DEFAUT))


def afficher_stations(rapport: RapportStations, detail: bool) -> None:
    print(f"Lignes lues        : {rapport.lignes_lues}")
    print(f"Lignes écartées    : {rapport.lignes_ecartees}")
    print(f"Stations retenues  : {len(rapport.stations)}")
    print(f"Stations exploitables (en service) : {len(rapport.exploitables)}")
    print("\nPar statut :")
    for statut, n in sorted(rapport.par_statut().items(), key=lambda p: p[0].value):
        print(f"  {statut.value:<14} {n:>4}")
    print("\nAnomalies :")
    for type_, n in rapport.par_type().most_common():
        decision = "corrigée" if type_ in CORRIGEABLES else "écartée"
        print(f"  {type_.value:<42} {n:>4}  {decision}")
    non_exploitables = [s for s in rapport.stations if not s.exploitable]
    if non_exploitables:
        print("\nStations retenues mais non exploitables :")
        for s in non_exploitables:
            print(f"  {s.code}  {s.nom} ({s.commune}) : {s.statut.value}")
    if detail:
        print("\nDétail :")
        for a in rapport.anomalies:
            print(f"  l.{a.ligne:<4} {a.code:<8} {a.type.name:<22} {a.detail}")


def afficher_journal(journal: Journal, detail: bool, titre: str = "Anomalies") -> None:
    print(f"{titre} :")
    for type_, n in journal.compteurs.most_common():
        decision = DECISIONS.get(type_, "gardée")
        print(f"  {type_.value:<52} {n:>7}  {decision}")
        if detail:
            for exemple in journal.exemples[type_]:
                print(f"      {exemple}")


def afficher_frequentation(
    freq: Frequentation, journal: Journal, noms: dict[str, str], detail: bool
) -> None:
    print(f"Trajets retenus : {freq.trajets}")
    for tj in TypeJour:
        print(f"Jours {tj.value:<9}: {freq.nb_jours(tj)}")
    print()
    afficher_journal(journal, detail)

    print("\nProfil horaire (moyenne par jour, tout le réseau)")
    print(f"  {'heure':>5}  {'départs sem.':>12} {'arrivées sem.':>13}  {'départs WE':>10}")
    semaine = freq.profil_horaire(TypeJour.SEMAINE)
    week_end = freq.profil_horaire(TypeJour.WEEK_END)
    for (h, dep, arr), (_, dep_we, _) in zip(semaine, week_end, strict=True):
        print(f"  {h:>4}h  {dep:>12.1f} {arr:>13.1f}  {dep_we:>10.1f}")

    print("\nStations qui se vident le matin (7h-10h) et se remplissent le soir (17h-20h),")
    print("en semaine, solde moyen de vélos par jour :")
    for code, matin, soir in stations_qui_se_vident(freq):
        nom = noms.get(code, "(non retenue)")
        print(f"  {code}  {nom:<28} matin {matin:+6.1f}   soir {soir:+6.1f}")


def euros(montant: Decimal) -> str:
    return f"{montant:,.2f}".replace(",", " ")


def afficher_facturation(
    facturation: Facturation,
    simulee: Facturation | None,
    journal_abonnes: Journal,
    detail: bool,
) -> None:
    abonnes = facturation.abonnes
    periodes = sum(len(p) for p in abonnes.periodes.values())
    print(f"Abonnés : {len(abonnes)} ({periodes} périodes d'abonnement)")
    afficher_journal(journal_abonnes, detail, "Anomalies de abonnes.jsonl")

    ca = facturation.ca
    formules = list(Formule)
    entete = "".join(f"{f.value:>13}" for f in formules)
    print("\nChiffre d'affaires en euros, par mois local de début du trajet :")
    print(f"  {'mois':<8}{entete}{'total':>13}{'dont pénalités':>16}")
    for mois in ca.mois():
        cases = "".join(f"{euros(ca.montants[mois, f]):>13}" for f in formules)
        print(f"  {mois:<8}{cases}{euros(ca.total(mois)):>13}{euros(ca.penalites[mois]):>16}")
    totaux = "".join(
        f"{euros(sum((v for (_, g), v in ca.montants.items() if g is f), Decimal(0))):>13}"
        for f in formules
    )
    penalites = sum(ca.penalites.values(), Decimal(0))
    print(f"  {'total':<8}{totaux}{euros(ca.total()):>13}{euros(penalites):>16}")

    print("\nTrajets facturés :")
    print(f"  {'mois':<8}{entete}{'total':>13}")
    for mois in ca.mois():
        cases = "".join(f"{ca.trajets[mois, f]:>13}" for f in formules)
        total = sum(ca.trajets[mois, f] for f in formules)
        print(f"  {mois:<8}{cases}{total:>13}")

    if simulee is not None:
        grille = max(g.en_vigueur_du for g in facturation.tarifs.grilles)
        mois = grille.strftime("%Y-%m")
        reel = ca.total(mois) - ca.penalites[mois]
        ancien = simulee.ca.total(mois) - simulee.ca.penalites[mois]
        ecart = reel - ancien
        print(f"\nGrille du {grille}, trajets de {mois} (hors pénalités) :")
        print(f"  avec la nouvelle grille  {euros(reel):>12}")
        print(f"  avec l'ancienne grille   {euros(ancien):>12}")
        print(f"  écart                    {euros(ecart):>12}  ({ecart / ancien:+.1%})")
        for f in formules:
            nouveau = ca.montants[mois, f] - simulee.ca.montants[mois, f]
            print(f"    {f.value:<12} {euros(nouveau):>12}")

    print()
    afficher_journal(facturation.journal, detail)
    print(f"\nAbonnés introuvables à signaler au service client : {len(facturation.introuvables)}")
    if detail:
        print("  " + " ".join(sorted(facturation.introuvables)))


def photographier(strategie: str, url: str, cle: str) -> Photo:
    if strategie == "sequentiel":
        return photographier_sequentiel(ClientBornes(url, cle))
    if strategie == "threads":
        return photographier_threads(ClientBornes(url, cle))
    return asyncio.run(photographier_asyncio(ClientBornesAsync(url, cle)))


def afficher_etat(photo: Photo, rapport: RapportStations, duree: float) -> None:
    print(f"Photo prise en {duree:.1f} s")
    print(f"Stations listées par l'API : {len(photo.codes)}, ont répondu : {len(photo.etats)}")
    for code, erreur in sorted(photo.injoignables.items()):
        print(f"  injoignable : {code} ({erreur})")
    print(f"\nStations vides ({len(photo.vides)}) :")
    for e in photo.vides:
        print(f"  {e.code}  {e.places_libres} places libres")
    print(f"Stations pleines ({len(photo.pleines)}) :")
    for e in photo.pleines:
        print(f"  {e.code}  {e.velos} vélos")
    ecarts = comparer(photo, rapport)
    print("\nComparaison avec le référentiel :")
    for libelle, codes in (
        ("retenues mais absentes de l'API", ecarts.absentes_api),
        ("dans l'API, absentes de stations.csv", ecarts.inconnues_referentiel),
        ("dans l'API, écartées du référentiel", ecarts.ecartees_referentiel),
        ("fermées ou hors service qui répondent", ecarts.non_exploitables_actives),
    ):
        print(f"  {libelle:<38}: {' '.join(codes) or '-'}")
    print(f"  {'capacité différente (vélos + places)':<38}: {len(ecarts.capacites)} stations")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mobilis", description=__doc__)
    parser.add_argument("--donnees", help="dossier des données du kit (sinon MOBILIS_DONNEES)")
    parser.add_argument(
        "--mesure", action="store_true", help="affiche durée et pic mémoire (tracemalloc)"
    )
    sous = parser.add_subparsers(dest="commande", required=True)
    stations = sous.add_parser("stations", help="référentiel des stations et anomalies")
    stations.add_argument("--detail", action="store_true", help="liste chaque anomalie")
    frequentation = sous.add_parser("frequentation", help="profil horaire et soldes des stations")
    frequentation.add_argument("--mois", help="ne garder qu'un mois, AAAA-MM")
    frequentation.add_argument("--detail", action="store_true", help="exemples par anomalie")
    facturation = sous.add_parser("facturation", help="chiffre d'affaires par mois et formule")
    facturation.add_argument("--mois", help="ne garder qu'un mois, AAAA-MM")
    facturation.add_argument("--detail", action="store_true", help="exemples par anomalie")

    etat = sous.add_parser("etat", help="état des stations en temps réel (API des bornes)")
    etat.add_argument("--url", default=os.environ.get("MOBILIS_API_URL", URL_API_PAR_DEFAUT))
    etat.add_argument("--cle", help="clé de l'API (sinon MOBILIS_API_CLE)")
    etat.add_argument(
        "--strategie", choices=("sequentiel", "threads", "asyncio"), default="threads"
    )
    etat.add_argument(
        "--comparer", action="store_true", help="mesure les trois stratégies l'une après l'autre"
    )

    args = parser.parse_args(argv)
    dossier = dossier_donnees(args.donnees)
    chemin_stations = dossier / "stations.csv"
    if not chemin_stations.is_file():
        parser.error(f"fichier introuvable : {chemin_stations}")
    if args.mesure:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        tracemalloc.start()
    try:
        rapport = lire_stations(chemin_stations)
        if args.commande == "stations":
            afficher_stations(rapport, args.detail)
        elif args.commande == "frequentation":
            commande_frequentation(parser, args, dossier, rapport)
        elif args.commande == "facturation":
            commande_facturation(parser, args, dossier, rapport)
        elif args.commande == "etat":
            commande_etat(parser, args, rapport)
    finally:
        tracemalloc.stop()
    return 0


def exiger(parser: argparse.ArgumentParser, *chemins: Path) -> None:
    for chemin in chemins:
        if not chemin.is_file():
            parser.error(f"fichier introuvable : {chemin}")


def commande_frequentation(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    dossier: Path,
    rapport: RapportStations,
) -> None:
    chemin_trajets = dossier / FICHIER_TRAJETS
    exiger(parser, chemin_trajets)
    journal = Journal()
    freq = analyser_trajets(chemin_trajets, journal, rapport.codes_lus, args.mois)
    noms = {s.code: s.nom for s in rapport.stations}
    afficher_frequentation(freq, journal, noms, args.detail)


def commande_facturation(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    dossier: Path,
    rapport: RapportStations,
) -> None:
    chemin_trajets = dossier / FICHIER_TRAJETS
    chemin_abonnes = dossier / FICHIER_ABONNES
    chemin_tarifs = dossier / FICHIER_TARIFS
    exiger(parser, chemin_trajets, chemin_abonnes, chemin_tarifs)
    journal_abonnes = Journal()
    abonnes = lire_abonnes(chemin_abonnes, journal_abonnes)
    tarifs = lire_tarifs(chemin_tarifs)
    fact = facturer_fichier(
        chemin_trajets, tarifs, abonnes, Journal(), rapport.codes_lus, args.mois
    )
    # Mêmes trajets, ancienne grille : l'effet de la hausse à comportement égal.
    grille = max(g.en_vigueur_du for g in tarifs.grilles)
    mois_grille = grille.strftime("%Y-%m")
    simulee = None
    if mois_grille in fact.ca.mois():
        simulee = facturer_fichier(
            chemin_trajets, tarifs.avant(grille), abonnes, Journal(), rapport.codes_lus, mois_grille
        )
    afficher_facturation(fact, simulee, journal_abonnes, args.detail)


def commande_etat(
    parser: argparse.ArgumentParser, args: argparse.Namespace, rapport: RapportStations
) -> None:
    cle = args.cle or os.environ.get("MOBILIS_API_CLE")
    if not cle:
        parser.error("clé de l'API absente : --cle ou variable MOBILIS_API_CLE")
    strategies = ("sequentiel", "threads", "asyncio") if args.comparer else (args.strategie,)
    for strategie in strategies:
        debut = time.perf_counter()
        try:
            photo = photographier(strategie, args.url, cle)
        except ErreurApi as e:
            # Les bornes en panne sont déjà gérées ; ici c'est l'API entière (liste des stations).
            parser.exit(1, f"API des bornes inaccessible ({args.url}) : {e}\n")
        duree = time.perf_counter() - debut
        print(f"{strategie:<11}: {duree:5.1f} s, {len(photo.etats)} stations")
    afficher_etat(photo, rapport, duree)
