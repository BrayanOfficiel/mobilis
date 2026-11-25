"""TP du module 3 : chronométrer un bloc, avec une classe puis avec @contextmanager."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Literal


class Chrono:
    def __init__(self, nom: str, horloge: Callable[[], float] = time.perf_counter) -> None:
        self.nom = nom
        self.horloge = horloge
        self.duree: float | None = None
        self._debut = 0.0

    def __enter__(self) -> Chrono:
        self._debut = self.horloge()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self.duree = self.horloge() - self._debut
        print(f"{self.nom} : {self.duree:.3f} s")
        # False : une exception du bloc continue de remonter, on a juste mesuré.
        return False


class Mesure:
    """Ce que renvoie la version générateur : la durée n'est connue qu'à la sortie."""

    def __init__(self) -> None:
        self.duree: float | None = None


@contextmanager
def chrono(nom: str, horloge: Callable[[], float] = time.perf_counter) -> Iterator[Mesure]:
    mesure = Mesure()
    debut = horloge()
    try:
        yield mesure
    finally:
        mesure.duree = horloge() - debut
        print(f"{nom} : {mesure.duree:.3f} s")


if __name__ == "__main__":
    with Chrono("classe") as c:
        sum(range(1_000_000))
    with chrono("générateur") as m:
        sum(range(1_000_000))
    print(c.duree, m.duree)
