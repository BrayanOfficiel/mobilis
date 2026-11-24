import csv
import gzip
import io
import os
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mobilis.journal import Journal
from mobilis.trajets import (
    COLONNES,
    PARIS,
    AnomalieTrajet,
    Frequentation,
    TypeJour,
    TypeVelo,
    analyser_trajets,
    coherents,
    convertir_trajets,
    dedoublonner,
    lire_instant,
    signaler_inconnues,
    stations_qui_se_vident,
)
from mobilis.trajets import (
    Trajet as T,
)

ENTETE = ",".join(COLONNES)


def trajet(
    tid: str = "T1",
    depart: str = "MB-0001",
    arrivee: str | None = "MB-0002",
    debut: str = "2026-09-07T08:00:00+02:00",
    minutes: int | None = 20,
) -> T:
    d = datetime.fromisoformat(debut)
    return T(
        trajet_id=tid,
        abonne_id=None,
        velo_id="V1",
        type_velo=TypeVelo.MECANIQUE,
        station_depart=depart,
        debut=d,
        station_arrivee=arrivee,
        fin=None if minutes is None else d + timedelta(minutes=minutes),
        distance_m=1000,
    )


def ecrire_gz(chemin: Path, lignes: list[str]) -> Path:
    with gzip.open(chemin, "wt", encoding="utf-8", newline="") as f:
        f.write("\n".join([ENTETE, *lignes]) + "\n")
    return chemin


@pytest.mark.parametrize(
    "texte",
    ["2026-08-01T00:54:42+02:00", "2026-07-31T22:54:42Z", "01/08/2026 00:54:42"],
)
def test_trois_formats_meme_instant(texte: str) -> None:
    assert lire_instant(texte) == datetime(2026, 7, 31, 22, 54, 42, tzinfo=UTC)


def test_format_local_en_hiver() -> None:
    assert lire_instant("05/10/2026 12:00:00").utcoffset() == timedelta(hours=2)
    assert lire_instant("30/10/2026 12:00:00").utcoffset() == timedelta(hours=1)


def test_instant_sans_fuseau_refuse() -> None:
    with pytest.raises(ValueError):
        lire_instant("2026-08-01T00:54:42")


def test_changement_heure_e6() -> None:
    t = T(
        trajet_id="T1",
        abonne_id="A1",
        velo_id="V1",
        type_velo=TypeVelo.MECANIQUE,
        station_depart="MB-0001",
        debut=lire_instant("2026-10-25T02:40:00+02:00"),
        station_arrivee="MB-0002",
        fin=lire_instant("2026-10-25T02:10:00+01:00"),
        distance_m=None,
    )
    assert t.duree == timedelta(minutes=30)


def test_conversion_ecarte_et_note() -> None:
    lignes = [
        "T1,A1,V1,mecanique,MB-0001,2026-08-01T08:00:00+02:00,MB-0002,01/08/2026 08:20:00,1500",
        "T2,,V2,trottinette,MB-0001,2026-08-01T08:00:00+02:00,MB-0002,2026-08-01T06:20:00Z,1500",
        "T3,,V3,electrique,MB-0001,hier,MB-0002,2026-08-01T06:20:00Z,1500",
        "T4,,V4,electrique,MB-0001,2026-08-01T08:00:00+02:00,,,",
        "T5,,V5,electrique,MB-0001",
    ]
    journal = Journal()
    lecteur = csv.DictReader(io.StringIO("\n".join([ENTETE, *lignes])))
    trajets = list(convertir_trajets(((lecteur.line_num, ligne) for ligne in lecteur), journal))
    assert [t.trajet_id for t in trajets] == ["T1", "T4"]
    assert trajets[0].duree == timedelta(minutes=20)
    assert trajets[1].fin is None and trajets[1].distance_m is None
    assert journal[AnomalieTrajet.LIGNE_INVALIDE] == 3
    assert journal[AnomalieTrajet.DATE_LOCALE] == 1
    assert journal[AnomalieTrajet.SANS_ARRIVEE] == 1
    assert journal.exemples[AnomalieTrajet.LIGNE_INVALIDE][0].startswith("ligne 3 :")


def test_dedoublonner() -> None:
    journal = Journal()
    entree = [trajet("T1"), trajet("T1"), trajet("T2"), trajet("T3"), trajet("T2")]
    assert [t.trajet_id for t in dedoublonner(entree, journal)] == ["T1", "T2", "T3"]
    assert journal[AnomalieTrajet.DOUBLON] == 2


def test_dedoublonner_limite_de_la_fenetre() -> None:
    entree = [trajet("T1"), trajet("T2"), trajet("T3"), trajet("T1")]
    assert len(list(dedoublonner(entree, Journal(), fenetre=2))) == 4


def test_coherents_et_stations_inconnues() -> None:
    journal = Journal()
    entree = [
        trajet("T1", minutes=-5),
        trajet("T2", arrivee="MB-0999"),
        trajet("T3", minutes=None, arrivee=None),
    ]
    sortie = list(signaler_inconnues(coherents(entree, journal), {"MB-0001", "MB-0002"}, journal))
    assert [t.trajet_id for t in sortie] == ["T2", "T3"]
    assert journal[AnomalieTrajet.HORODATAGE_INCOHERENT] == 1
    assert journal[AnomalieTrajet.STATION_INCONNUE] == 1


def test_frequentation_heure_locale_et_type_de_jour() -> None:
    freq = Frequentation()
    freq.ajouter(trajet(debut="2026-09-07T06:30:00Z"))  # lundi 8h30 à Paris
    freq.ajouter(trajet(debut="2026-09-12T10:00:00+02:00", minutes=None, arrivee=None))  # samedi
    assert freq.departs["MB-0001", TypeJour.SEMAINE, 8] == 1
    assert freq.arrivees["MB-0002", TypeJour.SEMAINE, 8] == 1
    assert freq.departs["MB-0001", TypeJour.WEEK_END, 10] == 1
    assert sum(freq.arrivees.values()) == 1
    assert (freq.nb_jours(TypeJour.SEMAINE), freq.nb_jours(TypeJour.WEEK_END)) == (1, 1)
    assert freq.profil_horaire(TypeJour.SEMAINE)[8] == (8, 1.0, 1.0)


def test_stations_qui_se_vident() -> None:
    freq = Frequentation()
    for jour in ("07", "08"):
        freq.ajouter(
            trajet(depart="MB-0001", arrivee="MB-0002", debut=f"2026-09-{jour}T08:00:00+02:00")
        )
        freq.ajouter(
            trajet(depart="MB-0001", arrivee="MB-0002", debut=f"2026-09-{jour}T08:10:00+02:00")
        )
        freq.ajouter(
            trajet(depart="MB-0002", arrivee="MB-0001", debut=f"2026-09-{jour}T18:00:00+02:00")
        )
    assert stations_qui_se_vident(freq) == [("MB-0001", -2.0, 1.0)]


def lignes_synthetiques(n: int) -> list[str]:
    """Toutes les combinaisons (station, jour, heure) apparaissent dès 1 680 lignes."""
    lignes = []
    lundi = datetime(2026, 9, 7, tzinfo=PARIS)
    for i in range(n):
        debut = lundi + timedelta(days=i // 240 % 7, hours=i % 24, minutes=i % 60)
        fin = debut + timedelta(minutes=15)
        station = i // 24 % 10
        lignes.append(
            f"T{i:08d},,V1,mecanique,MB-{station:04d},{debut.isoformat()},"
            f"MB-{(station + 1) % 10:04d},{fin.isoformat()},1200"
        )
    return lignes


def test_memoire_constante(tmp_path: Path) -> None:
    # Pas moins de 20 000 lignes : en dessous, les compteurs restent sous 256 (petits
    # entiers partagés par Python) et le pic de référence est sous-estimé.
    petit = ecrire_gz(tmp_path / "petit.csv.gz", lignes_synthetiques(20_000))
    gros = ecrire_gz(tmp_path / "gros.csv.gz", lignes_synthetiques(100_000))
    pics = []
    tracemalloc.start()
    try:
        for chemin in (petit, gros):
            tracemalloc.reset_peak()
            freq = analyser_trajets(chemin, Journal())
            pics.append(tracemalloc.get_traced_memory()[1])
            del freq
    finally:
        tracemalloc.stop()
    assert pics[1] < pics[0] * 1.1


def test_analyse_bout_en_bout(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    chemin = ecrire_gz(
        tmp_path / "trajets.csv.gz",
        [
            "T1,,V1,mecanique,MB-0001,2026-09-07T08:00:00+02:00,MB-0002,2026-09-07T08:20:00+02:00,900",
            "T1,,V1,mecanique,MB-0001,2026-09-07T08:00:00+02:00,MB-0002,2026-09-07T08:20:00+02:00,900",
            "T2,,V1,mecanique,MB-0001,2026-10-07T08:00:00+02:00,MB-0002,2026-10-07T07:20:00+02:00,900",
            "T3,,V1,mecanique,MB-0001,2026-10-07T08:00:00+02:00,MB-0002,2026-10-07T08:20:00+02:00,900",
        ],
    )
    journal = Journal()
    with caplog.at_level("INFO", logger="mobilis"):
        freq = analyser_trajets(chemin, journal, {"MB-0001", "MB-0002"}, mois="2026-09")
    assert freq.trajets == 1
    assert journal[AnomalieTrajet.DOUBLON] == 1
    assert journal[AnomalieTrajet.HORODATAGE_INCOHERENT] == 1
    assert "analyse des trajets" in caplog.text


def test_entete_inattendu(tmp_path: Path) -> None:
    chemin = tmp_path / "t.csv"
    chemin.write_text("id,debut\nT1,2026\n", encoding="utf-8")
    with pytest.raises(ValueError, match="en-tête"):
        analyser_trajets(chemin, Journal())


KIT = Path(os.environ.get("MOBILIS_DONNEES", "kit/donnees")) / "trajets_2026-08_2026-10.csv.gz"


@pytest.mark.skipif(not KIT.is_file(), reason="données du kit absentes")
def test_kit_reel() -> None:
    journal = Journal()
    freq = analyser_trajets(KIT, journal)
    assert freq.trajets == 154_868
    assert journal[AnomalieTrajet.DOUBLON] == 620
    assert len(freq.jours) == 92
