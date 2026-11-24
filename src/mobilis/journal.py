"""Journal des anomalies : compte chaque type et garde quelques exemples."""

from __future__ import annotations

from collections import Counter, defaultdict
from enum import Enum
from typing import Generic, TypeVar

E = TypeVar("E", bound=Enum)


class LigneRejetee(Exception, Generic[E]):
    """Levée par un convertisseur de ligne quand la ligne est inutilisable."""

    def __init__(self, type_: E, detail: str = "") -> None:
        super().__init__(detail)
        self.type = type_
        self.detail = detail


class Journal:
    """Compteurs par type d'anomalie, en mémoire bornée (quelques exemples par type)."""

    def __init__(self, exemples_max: int = 5) -> None:
        self.compteurs: Counter[Enum] = Counter()
        self.exemples: defaultdict[Enum, list[str]] = defaultdict(list)
        self.exemples_max = exemples_max

    def noter(self, type_: Enum, detail: str = "") -> None:
        self.compteurs[type_] += 1
        if detail and len(self.exemples[type_]) < self.exemples_max:
            self.exemples[type_].append(detail)

    def __getitem__(self, type_: Enum) -> int:
        return self.compteurs[type_]

    def __len__(self) -> int:
        return self.compteurs.total()
