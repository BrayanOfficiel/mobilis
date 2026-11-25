"""Données de test : un mini kit écrit dans un dossier temporaire.

Les fichiers du kit ne sont pas versionnés et la CI ne les a pas : les tests
fabriquent leurs propres fichiers, avec les mêmes formats (et les mêmes
défauts) que les vrais.
"""

import gzip
import json
from pathlib import Path

import pytest

from mobilis.facturation import Tarifs, lire_tarifs
from mobilis.stations import COLONNES as COLONNES_STATIONS
from mobilis.trajets import COLONNES as COLONNES_TRAJETS

# Extrait des grilles de la spécification (sans la formule solidaire).
ANNUEL_2025 = {
    "minutes_incluses": 30,
    "tranche_minutes": 30,
    "prix_tranche": "1.00",
    "supplement_electrique_tranche": "0.50",
    "frais_deblocage": "0.00",
    "plafond_jour": "12.00",
}
OCCASIONNEL_2025 = {
    "minutes_incluses": 0,
    "tranche_minutes": 15,
    "prix_tranche": "0.60",
    "supplement_electrique_tranche": "0.40",
    "frais_deblocage": "1.00",
    "plafond_jour": None,
}
TARIFS = {
    "devise": "EUR",
    "penalite_non_restitution": "150.00",
    "seuil_non_restitution_heures": 24,
    "grilles": [
        {
            "en_vigueur_du": "2025-01-01",
            "formules": {
                "annuel": ANNUEL_2025,
                "mensuel": {**ANNUEL_2025, "plafond_jour": "15.00"},
                "occasionnel": OCCASIONNEL_2025,
            },
        },
        {
            "en_vigueur_du": "2026-10-01",
            "formules": {
                "annuel": {**ANNUEL_2025, "prix_tranche": "1.20", "plafond_jour": "14.00"},
                "mensuel": {**ANNUEL_2025, "prix_tranche": "1.20", "plafond_jour": "18.00"},
                "occasionnel": {
                    **OCCASIONNEL_2025,
                    "prix_tranche": "0.75",
                    "supplement_electrique_tranche": "0.50",
                    "frais_deblocage": "1.20",
                },
            },
        },
    ],
}

STATIONS = [
    "MB-0001;Hôpital Lamartine;Valmont;20;45,78525;4,87212;En service ;16/12/2017",
    "MB-0002;Gare du Château;Valmont;30;45,76047;4,84165;en_service;2023-02-06",
    "MB-0003;Parc;Valmont;NC;45,76000;4,84000;HS;01/01/2020",
]
TRAJETS = [
    # abonné annuel, 40 min en septembre : 1 tranche, 1,00 €
    "T1,A1,V1,mecanique,MB-0001,2026-09-10T08:00:00+02:00,MB-0002,10/09/2026 08:40:00,900",
    "T1,A1,V1,mecanique,MB-0001,2026-09-10T08:00:00+02:00,MB-0002,10/09/2026 08:40:00,900",
    # E4 : occasionnel électrique 20 min en octobre, 3,70 € (3,00 € avec l'ancienne grille)
    "T2,,V2,electrique,MB-0002,2026-10-05T12:00:00Z,MB-0001,2026-10-05T12:20:00Z,",
    # abonné inconnu : occasionnel, 1,60 €
    "T3,A9,V3,mecanique,MB-0002,2026-09-10T09:00:00+02:00,MB-0001,2026-09-10T09:10:00+02:00,800",
    # non restitué : 150 €
    "T4,,V4,mecanique,MB-0001,2026-09-11T18:00:00+02:00,,,",
    # fin avant début : écarté
    "T5,,V5,mecanique,MB-0001,2026-09-12T18:00:00+02:00,MB-0002,2026-09-12T17:00:00+02:00,500",
]
ABONNES = [
    '{"id": "A1", "formule": "Annuel", "debut": "2025-01-01", "fin": null, "commune": "Valmont"}',
    "",
    '{"id": "A2", "formule": "mens',
]


@pytest.fixture
def tarifs(tmp_path: Path) -> Tarifs:
    chemin = tmp_path / "tarifs.json"
    chemin.write_text(json.dumps(TARIFS), encoding="utf-8")
    return lire_tarifs(chemin)


@pytest.fixture
def donnees(tmp_path: Path) -> Path:
    """Un dossier au format du kit : stations en cp1252 et CRLF, trajets compressés."""
    dossier = tmp_path / "donnees"
    dossier.mkdir()
    lignes = [";".join(COLONNES_STATIONS), *STATIONS]
    (dossier / "stations.csv").write_bytes("\r\n".join(lignes).encode("cp1252") + b"\r\n")
    with gzip.open(dossier / "trajets_2026-08_2026-10.csv.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join([",".join(COLONNES_TRAJETS), *TRAJETS]) + "\n")
    (dossier / "abonnes.jsonl").write_text("\n".join(ABONNES) + "\n", encoding="utf-8")
    (dossier / "tarifs.json").write_text(json.dumps(TARIFS), encoding="utf-8")
    return dossier
