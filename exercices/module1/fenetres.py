"""Exercice 2 du module 1 : fenêtres glissantes."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from typing import TypeVar

T = TypeVar("T")


def fenetres(iterable: Iterable[T], taille: int) -> Iterator[tuple[T, ...]]:
    """Produit les fenêtres glissantes de `taille` éléments consécutifs."""
    if taille < 1:
        raise ValueError("la taille doit être au moins 1")
    fenetre: deque[T] = deque(maxlen=taille)
    for element in iterable:
        fenetre.append(element)
        if len(fenetre) == taille:
            yield tuple(fenetre)


def moyennes_mobiles(valeurs: Iterable[float], taille: int) -> Iterator[float]:
    return (sum(f) / taille for f in fenetres(valeurs, taille))
