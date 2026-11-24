"""TP module 2 : décorateur de cache avec expiration."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Hashable
from typing import Any, Protocol, cast


class FonctionCachee(Protocol):
    __name__: str
    hits: int
    miss: int

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
    def vider(self) -> None: ...


def cache_ttl(
    duree_s: float, horloge: Callable[[], float] = time.monotonic
) -> Callable[[Callable[..., Any]], FonctionCachee]:
    if duree_s <= 0:
        raise ValueError("duree_s doit être positive")

    def decorateur(fn: Callable[..., Any]) -> FonctionCachee:
        cache: dict[Hashable, tuple[Any, float]] = {}

        @functools.wraps(fn)
        def enveloppe(*args: Any, **kwargs: Any) -> Any:
            cle = (args, tuple(sorted(kwargs.items())))
            if cle in cache:
                valeur, instant = cache[cle]
                if horloge() - instant < duree_s:
                    cachee.hits += 1
                    return valeur
            cachee.miss += 1
            valeur = fn(*args, **kwargs)
            # Horodatage pris APRÈS le calcul : la valeur reste valable duree_s pleines.
            cache[cle] = (valeur, horloge())
            return valeur

        # cachee est lue à l'appel (liaison tardive), pas à la définition d'enveloppe.
        cachee = cast(FonctionCachee, enveloppe)
        cachee.hits = 0
        cachee.miss = 0
        cachee.vider = cache.clear  # type: ignore[method-assign]
        return cachee

    return decorateur


if __name__ == "__main__":

    @cache_ttl(2)
    def lent(x: int) -> int:
        time.sleep(0.5)
        return x * 2

    debut = time.perf_counter()
    print(lent(3), lent(3), lent(4), f"{time.perf_counter() - debut:.2f} s", lent.hits, lent.miss)
