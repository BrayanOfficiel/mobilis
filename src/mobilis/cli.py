"""Commande `mobilis` : reproduit les chiffres du dossier à partir des fichiers bruts."""

from __future__ import annotations

import argparse
import logging
import os
import tracemalloc
from collections.abc import Sequence
from pathlib import Path

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
FICHIER_TRAJETS = "trajets_2026-08_2026-10.csv.gz"


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


def afficher_journal(journal: Journal, detail: bool) -> None:
    print("Anomalies :")
    for type_, n in journal.compteurs.most_common():
        decision = "écartée" if type_ in ECARTEES else "gardée"
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

    args = parser.parse_args(argv)
    dossier = dossier_donnees(args.donnees)
    chemin_stations = dossier / "stations.csv"
    if not chemin_stations.is_file():
        parser.error(f"fichier introuvable : {chemin_stations}")
    if args.mesure:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        tracemalloc.start()

    rapport = lire_stations(chemin_stations)
    if args.commande == "stations":
        afficher_stations(rapport, args.detail)
    elif args.commande == "frequentation":
        chemin_trajets = dossier / FICHIER_TRAJETS
        if not chemin_trajets.is_file():
            parser.error(f"fichier introuvable : {chemin_trajets}")
        journal = Journal()
        freq = analyser_trajets(chemin_trajets, journal, rapport.codes_lus, args.mois)
        noms = {s.code: s.nom for s in rapport.stations}
        afficher_frequentation(freq, journal, noms, args.detail)
    return 0
