import logging
import tracemalloc
from enum import Enum

import pytest

from mobilis.decorateurs import mesure, tolerante
from mobilis.journal import Journal, LigneRejetee


class Erreur(Enum):
    NEGATIF = "nombre négatif"


def test_mesure_garde_resultat_et_nom(caplog: pytest.LogCaptureFixture) -> None:
    @mesure("calcul")
    def calcul(x: int) -> int:
        """Double."""
        return 2 * x

    with caplog.at_level(logging.INFO, logger="mobilis"):
        assert calcul(4) == 8
    assert calcul.__name__ == "calcul" and calcul.__doc__ == "Double."
    assert "calcul :" in caplog.text and "pic mémoire" not in caplog.text


def test_mesure_memoire_et_exception(caplog: pytest.LogCaptureFixture) -> None:
    @mesure("allocation")
    def allouer() -> None:
        _ = [0] * 100_000
        raise RuntimeError("boum")

    tracemalloc.start()
    try:
        with caplog.at_level(logging.INFO, logger="mobilis"), pytest.raises(RuntimeError):
            allouer()
    finally:
        tracemalloc.stop()
    assert "allocation :" in caplog.text and "pic mémoire" in caplog.text


def test_tolerante_ecarte_et_continue() -> None:
    @tolerante
    def entier(texte: str, journal: Journal) -> int:
        valeur = int(texte)
        if valeur < 0:
            raise LigneRejetee(Erreur.NEGATIF, texte)
        return valeur

    journal = Journal(exemples_max=1)
    assert list(entier([(1, "3"), (2, "-1"), (3, "-2"), (4, "5")], journal)) == [3, 5]
    assert journal[Erreur.NEGATIF] == 2
    assert journal.exemples[Erreur.NEGATIF] == ["ligne 2 : -1"]
    assert len(journal) == 2
    with pytest.raises(ValueError):
        list(entier([(1, "x")], journal))
