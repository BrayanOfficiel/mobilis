"""Exercice 3 du module 2 : partial et reduce."""

from __future__ import annotations

import math
from functools import partial, reduce

arrondi2 = partial(round, ndigits=2)


def pgcd(nombres: list[int]) -> int:
    if not nombres:
        raise ValueError("liste vide")
    return reduce(math.gcd, nombres)
