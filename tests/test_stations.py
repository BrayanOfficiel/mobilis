import dataclasses
import os
from datetime import date
from pathlib import Path

import pytest

from mobilis.stations import (
    COLONNES,
    LigneRejetee,
    Station,
    Statut,
    TypeAnomalie,
    lire_station,
    lire_stations,
)

ENTETE = ";".join(COLONNES)
LIGNE_OK = "MB-0001;Gare Centrale;Valmont;20;45,76000;4,84000;En service;01/02/2020"


def ecrire_csv(dossier: Path, *lignes: str) -> Path:
    chemin = dossier / "stations.csv"
    chemin.write_bytes("\r\n".join((ENTETE, *lignes)).encode("cp1252") + b"\r\n")
    return chemin


def station(**changements: object) -> Station:
    base = Station(
        code="MB-0001",
        nom="Gare Centrale",
        commune="Valmont",
        capacite=20,
        latitude=45.76,
        longitude=4.84,
        statut=Statut.EN_SERVICE,
        mise_en_service=date(2020, 2, 1),
    )
    return dataclasses.replace(base, **changements)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("En service", Statut.EN_SERVICE),
        ("En service ", Statut.EN_SERVICE),
        ("en_service", Statut.EN_SERVICE),
        ("EN SERVICE", Statut.EN_SERVICE),
        ("Hors service", Statut.HORS_SERVICE),
        ("HS", Statut.HORS_SERVICE),
        ("FERMEE", Statut.FERMEE),
        ("Fermée", Statut.FERMEE),
    ],
)
def test_statut_depuis_texte(texte: str, attendu: Statut) -> None:
    assert Statut.depuis_texte(texte) is attendu


def test_statut_inconnu() -> None:
    with pytest.raises(ValueError, match="statut inconnu"):
        Statut.depuis_texte("en travaux")


def test_station_immuable_et_hachable() -> None:
    s = station()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.capacite = 30  # type: ignore[misc]
    assert len({s, station()}) == 1
    assert s.exploitable
    assert not station(statut=Statut.FERMEE).exploitable


@pytest.mark.parametrize(
    "changements",
    [
        {"code": "MB-12"},
        {"nom": ""},
        {"capacite": 0},
        {"latitude": 95.0},
    ],
)
def test_station_refuse_les_valeurs_invalides(changements: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        station(**changements)


def test_lire_station_corrige_espaces_date_iso_et_inversion() -> None:
    champs = "MB-0003;Rue des Forges  ; Valmont; 30;4,83156;45,77429;En service ;2024-05-22"
    s, corrections = lire_station(5, champs.split(";"))
    assert (s.nom, s.capacite, s.mise_en_service) == ("Rue des Forges", 30, date(2024, 5, 22))
    assert (s.latitude, s.longitude) == (45.77429, 4.83156)
    assert {a.type for a in corrections} == {
        TypeAnomalie.ESPACES,
        TypeAnomalie.DATE_ISO,
        TypeAnomalie.COORDONNEES_INVERSEES,
    }
    assert not any(a.ecartee for a in corrections)


@pytest.mark.parametrize(
    ("ligne", "type_attendu"),
    [
        (
            "MB-0028;Marché;Valmont;NC;45,79;4,82;en_service;30/05/2019",
            TypeAnomalie.CAPACITE_INVALIDE,
        ),
        ("MB-0109;Square;Valmont;32;;;En service;26/09/2015", TypeAnomalie.COORDONNEES_INVALIDES),
        (
            "MB-0010;Pont;Valmont;34;10,0;10,0;en_service;15/09/2018",
            TypeAnomalie.COORDONNEES_INVALIDES,
        ),
        ("MB-0010;Pont;Valmont;34;45,76;4,87;en_service;31/02/2018", TypeAnomalie.DATE_INVALIDE),
        ("MB-0010;Pont;Valmont;34;45,76;4,87;travaux;15/09/2018", TypeAnomalie.STATUT_INCONNU),
        ("MB-0010;Pont;Valmont;34;45,76;4,87", TypeAnomalie.NB_COLONNES),
        ("XX-0010;Pont;Valmont;34;45,76;4,87;en_service;15/09/2018", TypeAnomalie.VALEUR_INVALIDE),
    ],
)
def test_lire_station_rejette(ligne: str, type_attendu: TypeAnomalie) -> None:
    with pytest.raises(LigneRejetee) as erreur:
        lire_station(2, ligne.split(";"))
    assert erreur.value.type is type_attendu


def test_lire_stations_continue_apres_une_erreur(tmp_path: Path) -> None:
    chemin = ecrire_csv(
        tmp_path,
        LIGNE_OK,
        "MB-0002;Lycée Hugo;Bréval;NC;45,7;4,8;en_service;01/01/2020",
        "MB-0003;Hôpital Nord;Valmont;12;45,78;4,85;FERMEE;01/01/2021",
    )
    rapport = lire_stations(chemin)
    assert rapport.lignes_lues == 3
    assert rapport.lignes_ecartees == 1
    assert [s.code for s in rapport.stations] == ["MB-0001", "MB-0003"]
    assert [s.code for s in rapport.exploitables] == ["MB-0001"]
    assert rapport.stations[1].nom == "Hôpital Nord"


def test_doublon_garde_la_mise_en_service_la_plus_recente(tmp_path: Path) -> None:
    chemin = ecrire_csv(
        tmp_path,
        "MB-0033;Pont de la Mairie;Valmont;36;45,79;4,80;En service;16/09/2023",
        "MB-0068;Marché;Valmont;40;45,75;4,83;En service;26/04/2026",
        "MB-0033;Pont de la Mairie;Valmont;44;45,79;4,80;En service;28/11/2025",
        "MB-0068;Marché;Valmont;36;45,75;4,83;Hors service;15/05/2017",
    )
    rapport = lire_stations(chemin)
    assert {s.code: s.capacite for s in rapport.stations} == {"MB-0033": 44, "MB-0068": 40}
    doublons = [a for a in rapport.anomalies if a.type is TypeAnomalie.DOUBLON]
    assert [(a.ligne, a.code) for a in doublons] == [(2, "MB-0033"), (5, "MB-0068")]


def test_entete_inattendu(tmp_path: Path) -> None:
    chemin = tmp_path / "stations.csv"
    chemin.write_text("code,nom\nMB-0001,Gare\n", encoding="cp1252")
    with pytest.raises(ValueError, match="en-tête"):
        lire_stations(chemin)


KIT = Path(os.environ.get("MOBILIS_DONNEES", "kit/donnees")) / "stations.csv"


@pytest.mark.skipif(not KIT.is_file(), reason="données du kit absentes")
def test_kit_reel() -> None:
    rapport = lire_stations(KIT)
    assert rapport.lignes_lues == 153
    assert len(rapport.stations) == 147
    assert len({s.code for s in rapport.stations}) == len(rapport.stations)
    assert all(s.code != "MB-0028" for s in rapport.stations)
