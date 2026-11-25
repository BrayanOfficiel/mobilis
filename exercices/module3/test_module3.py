from decimal import Decimal
from pathlib import Path

import pytest
from chrono import Chrono, chrono
from compte import Compte
from intervalle import Intervalle, IntervalleModifiable
from lecteurs import ChampManquant, LecteurCSV, LecteurMemoire, compter, compter_tous
from mesure_slots import ReleveSlots
from transformateurs import Inverser, Majuscules, appliquer_tous


class Horloge:
    def __init__(self, *instants: float) -> None:
        self.instants = list(instants)

    def __call__(self) -> float:
        return self.instants.pop(0)


def test_chrono_classe_et_generateur() -> None:
    with Chrono("a", horloge=Horloge(1.0, 3.5)) as c:
        pass
    assert c.duree == 2.5
    with pytest.raises(ZeroDivisionError), chrono("b", horloge=Horloge(0.0, 1.0)) as m:
        raise ZeroDivisionError
    assert m.duree == 1.0


def test_compte_refuse_negatif_et_garde_son_etat() -> None:
    compte = Compte(Decimal("10"))
    with pytest.raises(ValueError):
        compte.solde = Decimal("-1")
    assert compte.solde == Decimal("10")
    assert not compte.decouvert
    with pytest.raises(TypeError):
        Compte(Decimal("NaN"))


def test_transformateurs() -> None:
    assert appliquer_tous("abc", [Majuscules(), Inverser()]) == "CBA"


def test_intervalles() -> None:
    with pytest.raises(ValueError):
        Intervalle(2, 1)
    i = IntervalleModifiable(0, 5)
    with pytest.raises(ValueError):
        i.deplacer(6, 5)
    assert (i.debut, i.fin) == (0, 5)


def test_lecteurs(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    a.write_text("id,nom\n1,x\n2,y\n", encoding="utf-8")
    with LecteurCSV(a, obligatoires=["id"]) as lecteur:
        assert compter(lecteur) == 2
    assert lecteur.fichier is not None and lecteur.fichier.closed
    assert compter(LecteurMemoire([{"id": "1"}])) == 1
    with pytest.raises(ChampManquant, match="ligne 2"):
        compter(LecteurMemoire([{"id": "1"}, {"id": ""}], obligatoires=["id"]))


def test_fichier_ferme_apres_erreur(tmp_path: Path) -> None:
    b = tmp_path / "b.csv"
    b.write_text("id\n1\n\n,\n", encoding="utf-8")
    lecteur = LecteurCSV(b, obligatoires=["id"])
    with pytest.raises(ChampManquant), lecteur:
        compter(lecteur)
    assert lecteur.fichier is not None and lecteur.fichier.closed


def test_exitstack_ferme_les_premiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ouverts = []
    chemins = []
    for nom in ("a", "b", "c"):
        chemin = tmp_path / f"{nom}.csv"
        chemin.write_text("id\n1\n", encoding="utf-8")
        chemins.append(chemin)
    chemins.append(tmp_path / "absent.csv")
    entrer = LecteurCSV.__enter__

    def espion(self: LecteurCSV) -> LecteurCSV:
        ouverts.append(self)
        return entrer(self)

    monkeypatch.setattr(LecteurCSV, "__enter__", espion)
    with pytest.raises(FileNotFoundError):
        compter_tous(chemins)
    assert len(ouverts) == 4
    assert all(lecteur.fichier.closed for lecteur in ouverts[:3] if lecteur.fichier)


def test_slots_refuse_attribut_inconnu() -> None:
    r = ReleveSlots("MB-0001", 3, 4)
    assert not hasattr(r, "__dict__")
    with pytest.raises(AttributeError):
        r.vitesse = 3  # type: ignore[attr-defined]
