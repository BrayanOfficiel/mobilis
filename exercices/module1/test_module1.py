from decimal import Decimal
from pathlib import Path

import pytest
from fenetres import fenetres, moyennes_mobiles
from tp_pipeline import Vente, filtrer, lire_ventes, total_par_produit
from vecteur import Vecteur2D

VENTES = Path(__file__).with_name("ventes.csv")


def test_vecteur_operations() -> None:
    v = Vecteur2D(3, 4)
    assert v + Vecteur2D(1, 1) == Vecteur2D(4, 5)
    assert v * 3 == 3 * v == Vecteur2D(9, 12)
    assert len(v) == 5
    assert abs(v) == 5.0
    assert repr(v) == "Vecteur2D(3, 4)"
    assert not Vecteur2D(0, 0)


def test_vecteur_hachable_et_comparaison_etrangere() -> None:
    assert len({Vecteur2D(1, 2), Vecteur2D(1, 2)}) == 1
    assert Vecteur2D(1, 2) != (1, 2)
    with pytest.raises(TypeError):
        Vecteur2D(1, 2) + 3  # type: ignore[operator]


def test_fenetres() -> None:
    assert list(fenetres([1, 2, 3, 4], 2)) == [(1, 2), (2, 3), (3, 4)]
    assert list(fenetres([1, 2], 3)) == []
    assert list(moyennes_mobiles([1.0, 2.0, 3.0], 2)) == [1.5, 2.5]


def test_fenetres_paresseux() -> None:
    gen = fenetres(iter(range(10**9)), 3)
    assert next(gen) == (0, 1, 2)


def test_fenetres_taille_invalide() -> None:
    with pytest.raises(ValueError):
        list(fenetres([1], 0))


def test_vente_montant() -> None:
    assert Vente("x", 3, Decimal("0.10")).montant == Decimal("0.30")


def test_pipeline() -> None:
    totaux = total_par_produit(filtrer(lire_ventes(VENTES), Decimal("20")))
    assert totaux == {
        "clavier": Decimal("74.70"),
        "souris": Decimal("49.95"),
        "ecran": Decimal("547.00"),
        "cable": Decimal("35.00"),
    }
