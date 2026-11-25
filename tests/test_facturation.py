import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from mobilis.abonnes import Abonnement, Abonnes, Formule
from mobilis.facturation import (
    AnomalieFacturation,
    Bareme,
    Facturation,
    TarifAbonnement,
    Tarifs,
    arrondir,
    lire_tarifs,
    tranches,
)
from mobilis.journal import Journal
from mobilis.trajets import Trajet, TypeVelo

# Extrait des grilles de la spécification (les données du kit ne sont pas versionnées).
ANNUEL_2025 = {
    "minutes_incluses": 30,
    "tranche_minutes": 30,
    "prix_tranche": "1.00",
    "supplement_electrique_tranche": "0.50",
    "frais_deblocage": "0.00",
    "plafond_jour": "12.00",
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
                "occasionnel": {
                    "minutes_incluses": 0,
                    "tranche_minutes": 15,
                    "prix_tranche": "0.60",
                    "supplement_electrique_tranche": "0.40",
                    "frais_deblocage": "1.00",
                    "plafond_jour": None,
                },
            },
        },
        {
            "en_vigueur_du": "2026-10-01",
            "formules": {
                "annuel": {**ANNUEL_2025, "prix_tranche": "1.20", "plafond_jour": "14.00"},
                "mensuel": {**ANNUEL_2025, "prix_tranche": "1.20", "plafond_jour": "18.00"},
                "occasionnel": {
                    "minutes_incluses": 0,
                    "tranche_minutes": 15,
                    "prix_tranche": "0.75",
                    "supplement_electrique_tranche": "0.50",
                    "frais_deblocage": "1.20",
                    "plafond_jour": None,
                },
            },
        },
    ],
}
ABONNES = Abonnes(
    [
        Abonnement("A-ANNUEL", Formule.ANNUEL, date(2025, 1, 1), None),
        Abonnement("A-MENSUEL", Formule.MENSUEL, date(2026, 9, 1), date(2026, 9, 30)),
    ]
)


@pytest.fixture
def tarifs(tmp_path: Path) -> Tarifs:
    chemin = tmp_path / "tarifs.json"
    chemin.write_text(json.dumps(TARIFS), encoding="utf-8")
    return lire_tarifs(chemin)


def trajet(
    debut: str,
    fin: str | None,
    abonne: str | None = "A-ANNUEL",
    velo: TypeVelo = TypeVelo.MECANIQUE,
    tid: str = "T1",
    arrivee: str = "MB-0002",
) -> Trajet:
    return Trajet(
        trajet_id=tid,
        abonne_id=abonne,
        velo_id="V1",
        type_velo=velo,
        station_depart="MB-0001",
        debut=datetime.fromisoformat(debut),
        station_arrivee=None if fin is None else arrivee,
        fin=None if fin is None else datetime.fromisoformat(fin),
        distance_m=None,
    )


def de_duree(
    debut: str,
    minutes: float,
    abonne: str | None = "A-ANNUEL",
    velo: TypeVelo = TypeVelo.MECANIQUE,
    tid: str = "T1",
    arrivee: str = "MB-0002",
) -> Trajet:
    fin = datetime.fromisoformat(debut) + timedelta(minutes=minutes)
    return trajet(debut, fin.isoformat(), abonne, velo, tid, arrivee)


SEPT = "2026-09-10T09:00:00+02:00"


@pytest.mark.parametrize(
    ("trajets", "attendu"),
    [
        pytest.param([de_duree(SEPT, 25)], "0.00", id="E1"),
        pytest.param([de_duree(SEPT, 25, velo=TypeVelo.ELECTRIQUE)], "0.50", id="E2"),
        pytest.param([de_duree(SEPT, 61, abonne="A-MENSUEL")], "2.00", id="E3"),
        pytest.param(
            [de_duree("2026-10-05T14:00:00+02:00", 20, abonne=None, velo=TypeVelo.ELECTRIQUE)],
            "3.70",
            id="E4",
        ),
        pytest.param(
            [de_duree(f"2026-08-12T{h:02d}:00:00+02:00", 180, tid=f"T{h}") for h in (6, 10, 14)],
            "12.00",
            id="E5",
        ),
        pytest.param(
            [trajet("2026-10-25T02:40:00+02:00", "2026-10-25T02:10:00+01:00")], "0.00", id="E6"
        ),
    ],
)
def test_exemples_de_la_specification(tarifs: Tarifs, trajets: list[Trajet], attendu: str) -> None:
    facturation = Facturation(tarifs, ABONNES, Journal())
    total = sum((facturation.facturer(t) for t in trajets), Decimal(0))
    assert total == Decimal(attendu)


def test_tranche_entamee_d_une_seconde() -> None:
    trente = timedelta(minutes=30)
    assert tranches(timedelta(0), trente) == 0
    assert tranches(trente, trente) == 1
    assert tranches(trente + timedelta(seconds=1), trente) == 2


def test_arrondi_moitie_vers_le_haut() -> None:
    assert arrondir(Decimal("0.125")) == Decimal("0.13")
    assert arrondir(Decimal("0.124")) == Decimal("0.12")


def test_lecture_tarifs_sans_float(tarifs: Tarifs) -> None:
    occasionnel = tarifs.grille(date(2026, 10, 1)).baremes[Formule.OCCASIONNEL]
    assert occasionnel.prix_tranche == Decimal("0.75")
    assert isinstance(occasionnel.prix_tranche, Decimal)
    assert tarifs.grille(date(2026, 9, 30)).en_vigueur_du == date(2025, 1, 1)
    with pytest.raises(ValueError):
        tarifs.grille(date(2024, 12, 31))


def test_grille_choisie_a_la_date_locale(tarifs: Tarifs) -> None:
    # 30/09 à 23h30 UTC, c'est déjà le 1er octobre à Paris : nouvelle grille.
    t = de_duree("2026-09-30T23:30:00+00:00", 10, abonne=None)
    assert Facturation(tarifs, ABONNES, Journal()).facturer(t) == Decimal("1.95")


def test_abonnement_expire_et_introuvable(tarifs: Tarifs) -> None:
    journal = Journal()
    facturation = Facturation(tarifs, ABONNES, journal)
    oct = "2026-10-05T14:00:00+02:00"
    assert facturation.facturer(de_duree(oct, 10, abonne="A-MENSUEL")) == Decimal("1.95")
    assert facturation.facturer(de_duree(oct, 10, abonne="A-INCONNU")) == Decimal("1.95")
    assert journal[AnomalieFacturation.ABONNEMENT_INACTIF] == 1
    assert journal[AnomalieFacturation.ABONNE_INTROUVABLE] == 1
    assert facturation.introuvables == {"A-INCONNU"}


def test_fantome_et_non_restitution(tarifs: Tarifs) -> None:
    journal = Journal()
    facturation = Facturation(tarifs, ABONNES, journal)
    fantome = de_duree(SEPT, 1.5, abonne=None, arrivee="MB-0001")
    court_ailleurs = de_duree(SEPT, 1.5, abonne=None, tid="T2")
    perdu = trajet(SEPT, None, tid="T3")
    trop_long = de_duree(SEPT, 24 * 60 + 1, tid="T4")
    assert facturation.facturer(fantome) == Decimal("0.00")
    assert facturation.facturer(court_ailleurs) == Decimal("1.60")
    assert facturation.facturer(perdu) == Decimal("150.00")
    assert facturation.facturer(trop_long) == Decimal("150.00")
    assert journal[AnomalieFacturation.FANTOME] == 1
    assert journal[AnomalieFacturation.NON_RESTITUTION] == 2
    assert facturation.ca.penalites["2026-09"] == Decimal("300.00")


def test_penalite_hors_plafond(tarifs: Tarifs) -> None:
    facturation = Facturation(tarifs, ABONNES, Journal())
    for h in (6, 10, 14):
        facturation.facturer(de_duree(f"2026-08-12T{h:02d}:00:00+02:00", 180, tid=f"T{h}"))
    assert facturation.facturer(trajet("2026-08-12T18:00:00+02:00", None)) == Decimal("150")
    assert facturation.ca.total("2026-08") == Decimal("162.00")


def test_plafond_par_jour_local_et_par_abonne(tarifs: Tarifs) -> None:
    facturation = Facturation(tarifs, ABONNES, Journal())
    # 23h30 et 00h30 le lendemain (heure de Paris) : deux journées, deux plafonds.
    soir = de_duree("2026-08-12T23:30:00+02:00", 600, tid="T1")
    lendemain = de_duree("2026-08-13T00:30:00+02:00", 600, tid="T2")
    assert facturation.facturer(soir) == Decimal("12.00")
    assert facturation.facturer(lendemain) == Decimal("12.00")


def test_abonnement_sans_plafond_refuse() -> None:
    bareme = Bareme.depuis_json({**ANNUEL_2025, "plafond_jour": None})
    with pytest.raises(ValueError):
        TarifAbonnement(bareme)


def test_chiffre_affaires_par_mois_et_formule(tarifs: Tarifs) -> None:
    facturation = Facturation(tarifs, ABONNES, Journal())
    ca = facturation.facturer_tous(
        [
            de_duree(SEPT, 61, abonne="A-MENSUEL"),
            de_duree("2026-10-05T14:00:00+02:00", 20, abonne=None, tid="T2"),
        ]
    )
    assert ca.mois() == ["2026-09", "2026-10"]
    assert ca.montants["2026-09", Formule.MENSUEL] == Decimal("2.00")
    assert ca.total() == Decimal("4.70")


def test_ancienne_grille_pour_simuler_octobre(tarifs: Tarifs) -> None:
    ancienne = tarifs.avant(date(2026, 10, 1))
    t = de_duree("2026-10-05T14:00:00+02:00", 20, abonne=None, velo=TypeVelo.ELECTRIQUE)
    assert Facturation(ancienne, ABONNES, Journal()).facturer(t) == Decimal("3.00")


KIT = Path(os.environ.get("MOBILIS_DONNEES", "kit/donnees"))


@pytest.mark.skipif(not (KIT / "tarifs.json").is_file(), reason="données du kit absentes")
def test_tarifs_du_kit() -> None:
    tarifs = lire_tarifs(KIT / "tarifs.json")
    assert len(tarifs.grilles) == 2
    assert tarifs.grille(date(2026, 10, 1)).baremes[Formule.SOLIDAIRE].plafond_jour == Decimal(5)
