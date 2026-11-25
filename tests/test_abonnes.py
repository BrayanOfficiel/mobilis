import os
from datetime import date
from pathlib import Path

import pytest

from mobilis.abonnes import (
    Abonnement,
    Abonnes,
    AnomalieAbonne,
    Formule,
    lire_abonnes,
)
from mobilis.journal import Journal

LIGNES = [
    '{"id": "A1", "formule": "annuel", "debut": "2025-01-01", "fin": null, "commune": "X"}',
    '{"id": "A2", "formule": " Mensuel", "debut": "2026-09-01", "fin": "2026-09-30"}',
    "",
    '{"id": "A3", "formule": "annuel", "debut": "2024-01-01", "fin": "2024-12-31", "commune": "Le',
    '{"id": "A4", "formule": "annuel", "',
    '{"id": "A5", "formule": "occasionnel", "debut": "2026-01-01", "fin": null}',
    '{"id": "A6", "formule": "annuel", "debut": "2026-05-01", "fin": "2026-04-01"}',
    '["pas", "un", "objet"]',
    '{"id": "A1", "formule": "solidaire", "debut": "2023-01-01", "fin": "2024-12-31"}',
]


def test_lecture_tolerante(tmp_path: Path) -> None:
    chemin = tmp_path / "abonnes.jsonl"
    chemin.write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    journal = Journal()
    abonnes = lire_abonnes(chemin, journal)
    assert sorted(abonnes.periodes) == ["A1", "A2", "A3"]
    assert len(abonnes.periodes["A1"]) == 2
    assert journal[AnomalieAbonne.FORMULE_NORMALISEE] == 1
    assert journal[AnomalieAbonne.LIGNE_VIDE] == 1
    assert journal[AnomalieAbonne.TRONQUEE_RECUPEREE] == 1
    assert journal[AnomalieAbonne.TRONQUEE] == 1
    assert journal[AnomalieAbonne.LIGNE_INVALIDE] == 3
    assert journal.exemples[AnomalieAbonne.TRONQUEE] == ["ligne 5 : A4"]


def test_formule_active_bornes_incluses() -> None:
    abonnes = Abonnes(
        [
            Abonnement("A1", Formule.MENSUEL, date(2026, 9, 1), date(2026, 9, 30)),
            Abonnement("A1", Formule.ANNUEL, date(2026, 10, 1), None),
        ]
    )
    assert abonnes.formule("A1", date(2026, 8, 31)) is None
    assert abonnes.formule("A1", date(2026, 9, 30)) is Formule.MENSUEL
    assert abonnes.formule("A1", date(2027, 6, 1)) is Formule.ANNUEL
    assert abonnes.formule("A9", date(2026, 9, 1)) is None
    assert "A1" in abonnes and "A9" not in abonnes


KIT = Path(os.environ.get("MOBILIS_DONNEES", "kit/donnees")) / "abonnes.jsonl"


@pytest.mark.skipif(not KIT.is_file(), reason="données du kit absentes")
def test_kit_reel() -> None:
    journal = Journal()
    abonnes = lire_abonnes(KIT, journal)
    assert len(abonnes) == 5196
    assert journal[AnomalieAbonne.TRONQUEE] == 4
    assert journal[AnomalieAbonne.TRONQUEE_RECUPEREE] == 2
