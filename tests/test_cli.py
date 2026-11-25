"""La commande `mobilis` de bout en bout, sur le mini kit de conftest.py."""

import re
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import pytest

from mobilis.bornes import ErreurApi, EtatStation, Photo
from mobilis.cli import dossier_donnees, main


def test_dossier_des_donnees(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOBILIS_DONNEES", raising=False)
    assert dossier_donnees(None) == Path("kit/donnees")
    monkeypatch.setenv("MOBILIS_DONNEES", "/ailleurs")
    assert dossier_donnees(None) == Path("/ailleurs")
    assert dossier_donnees("/option") == Path("/option")


def test_fichier_absent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as sortie:
        main(["--donnees", str(tmp_path), "stations"])
    assert sortie.value.code == 2
    assert "fichier introuvable" in capsys.readouterr().err


def test_stations(donnees: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--donnees", str(donnees), "stations"]) == 0
    sortie = capsys.readouterr().out
    assert "Stations retenues  : 2" in sortie
    assert "Lignes écartées    : 1" in sortie


def test_frequentation_avec_mesure(
    donnees: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="mobilis"):
        assert main(["--mesure", "--donnees", str(donnees), "frequentation"]) == 0
    sortie = capsys.readouterr().out
    assert "Trajets retenus : 4" in sortie
    assert "trajet déjà transmis" in sortie
    assert "pic mémoire" in caplog.text


def test_facturation(donnees: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--donnees", str(donnees), "facturation", "--detail"]) == 0
    sortie = capsys.readouterr().out
    # Première ligne de chaque mois : le tableau des montants (le second compte les trajets).
    lignes: dict[str, list[str]] = {}
    for ligne in sortie.splitlines():
        if ligne.strip():
            lignes.setdefault(ligne.split()[0], ligne.split())
    # septembre : 1,00 (annuel) + 1,60 (abonné inconnu) + 150 (non restitué)
    assert lignes["2026-09"][-2:] == ["152.60", "150.00"]
    assert lignes["2026-10"][-2:] == ["3.70", "0.00"]
    assert re.search(r"avec l'ancienne grille +3\.00", sortie)
    assert "Abonnés introuvables à signaler au service client : 1" in sortie
    assert "  A9" in sortie
    assert "ligne tronquée, champs utiles perdus" in sortie


def photo_test() -> Photo:
    photo = Photo()
    photo.ajouter(
        "MB-0001",
        EtatStation("MB-0001", 0, 0, 20, datetime(2026, 11, 25, tzinfo=UTC)),
    )
    photo.ajouter("MB-0002", ErreurApi(504, "borne injoignable"))
    return photo


def test_etat_sans_serveur(
    donnees: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOBILIS_API_CLE", "cle-de-test")
    with mock.patch("mobilis.cli.photographier", return_value=photo_test()) as photographier:
        assert main(["--donnees", str(donnees), "etat"]) == 0
    photographier.assert_called_once_with("threads", "http://127.0.0.1:8765", "cle-de-test")
    sortie = capsys.readouterr().out
    assert "Stations vides (1)" in sortie
    assert "injoignable : MB-0002" in sortie


def test_etat_sans_cle(
    donnees: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MOBILIS_API_CLE", raising=False)
    with pytest.raises(SystemExit):
        main(["--donnees", str(donnees), "etat"])
    assert "clé de l'API absente" in capsys.readouterr().err


def test_etat_api_eteinte(
    donnees: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOBILIS_API_CLE", "cle-de-test")
    erreur = ErreurApi(None, "réseau : connexion refusée")
    with mock.patch("mobilis.cli.photographier", side_effect=erreur), pytest.raises(SystemExit):
        main(["--donnees", str(donnees), "etat"])
    assert "API des bornes inaccessible" in capsys.readouterr().err
