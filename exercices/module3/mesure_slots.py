"""Atelier du module 3, livrable 5 : dataclass ordinaire contre slots=True."""

from __future__ import annotations

import sys
import time
import tracemalloc
from dataclasses import dataclass


@dataclass
class Releve:
    station: str
    velos: int
    places: int


@dataclass(slots=True)
class ReleveSlots:
    station: str
    velos: int
    places: int


def mesurer(cls: type[Releve] | type[ReleveSlots], n: int) -> tuple[float, int]:
    tracemalloc.start()
    debut = time.perf_counter()
    lot = [cls("MB-0001", i % 30, 30 - i % 30) for i in range(n)]
    duree = time.perf_counter() - debut
    memoire = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    del lot
    return duree, memoire


if __name__ == "__main__":
    n = 1_000_000
    print(sys.version.split()[0])
    for cls in (Releve, ReleveSlots):
        meilleur = min(mesurer(cls, n) for _ in range(3))
        print(f"{cls.__name__:<12} {meilleur[0]:.3f} s  {meilleur[1] / 2**20:6.1f} Mio")
