import pytest
from cache_ttl import cache_ttl
from fonctionnel import arrondi2, pgcd
from memoize import fib, fib_memo, memoize
from tracer import trace


class Horloge:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_cache_ttl_expire() -> None:
    horloge = Horloge()
    appels = []

    @cache_ttl(10, horloge=horloge)
    def carre(x: int) -> int:
        appels.append(x)
        return x * x

    assert carre(3) == carre(3) == 9
    assert (carre.hits, carre.miss) == (1, 1)
    horloge.t = 10
    assert carre(3) == 9
    assert appels == [3, 3]
    carre.vider()
    carre(3)
    assert carre.miss == 3
    assert carre.__name__ == "carre"


def test_cache_ttl_cle_avec_kwargs() -> None:
    @cache_ttl(5, horloge=Horloge())
    def f(a: int, b: int = 0) -> int:
        return a + b

    f(1, b=2)
    f(1, b=2)
    f(1, b=3)
    assert (f.hits, f.miss) == (1, 2)


def test_cache_ttl_duree_invalide() -> None:
    with pytest.raises(ValueError):
        cache_ttl(0)


def test_trace(capsys: pytest.CaptureFixture[str]) -> None:
    @trace
    def ajouter(a: int, b: int = 1) -> int:
        """Ajoute."""
        return a + b

    assert ajouter(2, b=3) == 5
    assert capsys.readouterr().out == "ajouter(2, b=3)\najouter -> 5\n"
    assert ajouter.__name__ == "ajouter"
    assert ajouter.__doc__ == "Ajoute."


def test_memoize() -> None:
    assert fib_memo(80) == 23416728348467685
    assert fib(20) == fib_memo(20)
    compteur = []

    @memoize
    def double(x: int) -> int:
        compteur.append(x)
        return 2 * x

    double(4)
    double(4)
    assert compteur == [4]


def test_partial_et_reduce() -> None:
    assert arrondi2(3.14159) == 3.14
    assert pgcd([12, 18, 24]) == 6
    with pytest.raises(ValueError):
        pgcd([])
