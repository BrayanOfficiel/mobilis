"""Exercice 1 du module 1 : une classe pythonique."""

from __future__ import annotations

import math


class Vecteur2D:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Vecteur2D({self.x!r}, {self.y!r})"

    def __eq__(self, autre: object) -> bool:
        if not isinstance(autre, Vecteur2D):
            return NotImplemented
        return (self.x, self.y) == (autre.x, autre.y)

    # __eq__ redéfini sans __hash__ rendrait la classe non hachable.
    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __add__(self, autre: Vecteur2D) -> Vecteur2D:
        if not isinstance(autre, Vecteur2D):
            return NotImplemented
        return Vecteur2D(self.x + autre.x, self.y + autre.y)

    def __mul__(self, k: float) -> Vecteur2D:
        if not isinstance(k, (int, float)):
            return NotImplemented
        return Vecteur2D(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __abs__(self) -> float:
        return math.hypot(self.x, self.y)

    def __len__(self) -> int:
        # len() doit renvoyer un entier positif : on arrondit la norme.
        return round(abs(self))

    def __bool__(self) -> bool:
        return bool(self.x or self.y)
