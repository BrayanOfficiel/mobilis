"""Exercices 1 et 2 du module 5."""

from __future__ import annotations

import logging
from typing import Protocol

journal = logging.getLogger(__name__)


def est_palindrome(texte: str) -> bool:
    lettres = "".join(texte.lower().split())
    return lettres == lettres[::-1]


class Depot(Protocol):
    def save(self, article: object) -> None: ...


def enregistrer(depot: Depot, article: object) -> bool:
    try:
        depot.save(article)
    except Exception:
        # Le dépôt peut échouer de mille façons (réseau, disque) : on trace et on rend False.
        journal.exception("enregistrement impossible")
        return False
    return True
