"""Exercice 2 du module 2 : mémoïsation sans lru_cache."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Hashable
from typing import TypeVar

R = TypeVar("R")


def memoize(fn: Callable[..., R]) -> Callable[..., R]:
    cache: dict[Hashable, R] = {}

    @functools.wraps(fn)
    def enveloppe(*args: Hashable) -> R:
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]

    return enveloppe


def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


@memoize
def fib_memo(n: int) -> int:
    # L'appel récursif passe par le nom décoré, donc par le cache.
    return n if n < 2 else fib_memo(n - 1) + fib_memo(n - 2)


if __name__ == "__main__":
    for f in (fib, fib_memo):
        debut = time.perf_counter()
        resultat = f(35)
        print(f"{f.__name__}(35) = {resultat} en {time.perf_counter() - debut:.4f} s")
