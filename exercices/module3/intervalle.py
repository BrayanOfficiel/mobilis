"""Exercice A du module 3 : deux façons de garder debut <= fin."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Intervalle:
    """Immuable : l'invariant n'est vérifié qu'une fois, à la construction."""

    debut: float
    fin: float

    def __post_init__(self) -> None:
        if self.debut > self.fin:
            raise ValueError(f"debut {self.debut} > fin {self.fin}")


class IntervalleModifiable:
    """Mutable : les bornes changent ensemble, par une seule méthode qui valide."""

    def __init__(self, debut: float, fin: float) -> None:
        self.deplacer(debut, fin)

    @property
    def debut(self) -> float:
        return self._debut

    @property
    def fin(self) -> float:
        return self._fin

    def deplacer(self, debut: float, fin: float) -> None:
        if debut > fin:
            raise ValueError(f"debut {debut} > fin {fin}")
        self._debut, self._fin = debut, fin
