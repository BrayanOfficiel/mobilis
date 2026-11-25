"""Exercice 2 du module 3 : un registre de transformateurs typé par Protocol."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class Transformateur(Protocol):
    def transformer(self, texte: str) -> str: ...


class Majuscules:
    def transformer(self, texte: str) -> str:
        return texte.upper()


class Inverser:
    def transformer(self, texte: str) -> str:
        return texte[::-1]


def appliquer_tous(texte: str, transformateurs: Iterable[Transformateur]) -> str:
    for t in transformateurs:
        texte = t.transformer(texte)
    return texte
