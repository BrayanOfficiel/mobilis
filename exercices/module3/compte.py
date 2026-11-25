"""Exercice 1 du module 3 : un solde protégé par une property."""

from __future__ import annotations

from decimal import Decimal


class Compte:
    def __init__(self, solde: Decimal = Decimal("0")) -> None:
        self.solde = solde

    @property
    def solde(self) -> Decimal:
        return self._solde

    @solde.setter
    def solde(self, valeur: Decimal) -> None:
        if not isinstance(valeur, Decimal) or not valeur.is_finite():
            raise TypeError("le solde est un Decimal fini")
        if valeur < 0:
            raise ValueError("le solde ne peut pas être négatif")
        self._solde = valeur

    @property
    def decouvert(self) -> bool:
        return self._solde < 0
