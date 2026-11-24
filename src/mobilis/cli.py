"""Commande `mobilis` : reproduit les chiffres du dossier à partir des fichiers bruts."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from mobilis.stations import CORRIGEABLES, RapportStations, lire_stations

DONNEES_PAR_DEFAUT = Path("kit/donnees")


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mobilis", description=__doc__)
    parser.add_argument("--donnees", help="dossier des données du kit (sinon MOBILIS_DONNEES)")
    sous = parser.add_subparsers(dest="commande", required=True)
    stations = sous.add_parser("stations", help="référentiel des stations et anomalies")
    stations.add_argument("--detail", action="store_true", help="liste chaque anomalie")

    args = parser.parse_args(argv)
    chemin = dossier_donnees(args.donnees) / "stations.csv"
    if not chemin.is_file():
        parser.error(f"fichier introuvable : {chemin}")
    if args.commande == "stations":
        afficher_stations(lire_stations(chemin), args.detail)
    return 0
