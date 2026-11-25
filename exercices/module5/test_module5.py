from unittest.mock import Mock

import pytest
from exos import enregistrer, est_palindrome
from panier import Article, Panier


@pytest.fixture
def panier_rempli() -> Panier:
    p = Panier()
    p.ajouter(Article("stylo", 1.5, 3))
    p.ajouter(Article("cahier", 2.0, 2))
    return p


def test_total_panier(panier_rempli: Panier) -> None:
    assert panier_rempli.total() == 8.5


@pytest.mark.parametrize(("remise", "attendu"), [(0, 8.5), (10, 7.65), (50, 4.25), (100, 0.0)])
def test_remise(panier_rempli: Panier, remise: float, attendu: float) -> None:
    assert panier_rempli.appliquer_remise(remise) == pytest.approx(attendu)


@pytest.mark.parametrize("remise", [-1, 150])
def test_remise_invalide(panier_rempli: Panier, remise: float) -> None:
    with pytest.raises(ValueError):
        panier_rempli.appliquer_remise(remise)


def test_article_le_plus_cher(panier_rempli: Panier) -> None:
    plus_cher = panier_rempli.article_le_plus_cher()
    assert plus_cher is not None and plus_cher.nom == "stylo"
    assert Panier().article_le_plus_cher() is None


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [("kayak", True), ("Esope reste ici et se repose", True), ("", True), ("python", False)],
)
def test_palindrome(texte: str, attendu: bool) -> None:
    assert est_palindrome(texte) is attendu


def test_enregistrer_succes() -> None:
    depot = Mock()
    assert enregistrer(depot, "a") is True
    depot.save.assert_called_once_with("a")


def test_enregistrer_echec(caplog: pytest.LogCaptureFixture) -> None:
    depot = Mock()
    depot.save.side_effect = OSError("disque plein")
    assert enregistrer(depot, "a") is False
    assert "enregistrement impossible" in caplog.text
