"""Exercice 1 du module 2 : décorateur de journalisation."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def trace(fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def enveloppe(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
        print(f"{fn.__name__}({', '.join(arguments)})")
        resultat = fn(*args, **kwargs)
        print(f"{fn.__name__} -> {resultat!r}")
        return resultat

    return enveloppe
