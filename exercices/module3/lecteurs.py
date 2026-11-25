"""Atelier du module 3 : lecteurs d'enregistrements interchangeables."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from pathlib import Path
from types import TracebackType
from typing import Protocol, TextIO


class LecteurEnregistrements(Protocol):
    """Le seul besoin du code appelant : itérer sur des dictionnaires."""

    def enregistrements(self) -> Iterator[dict[str, str]]: ...


class ChampManquant(ValueError):
    def __init__(self, source: str, ligne: int, champ: str) -> None:
        # Pas le contenu de la ligne dans le message : il peut contenir des données client.
        super().__init__(f"{source}, ligne {ligne} : champ {champ!r} vide ou absent")


def verifier(source: str, ligne: int, rec: dict[str, str], obligatoires: Sequence[str]) -> None:
    for champ in obligatoires:
        if not rec.get(champ):
            raise ChampManquant(source, ligne, champ)


class LecteurCSV:
    """Possède un fichier ouvert : c'est un gestionnaire de contexte."""

    def __init__(self, chemin: Path, obligatoires: Sequence[str] = (), encodage: str = "utf-8"):
        self.chemin = chemin
        self.obligatoires = obligatoires
        self.encodage = encodage
        self.fichier: TextIO | None = None

    def __enter__(self) -> LecteurCSV:
        self.fichier = self.chemin.open(encoding=self.encodage, newline="")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.fichier is not None:
            self.fichier.close()

    def enregistrements(self) -> Iterator[dict[str, str]]:
        if self.fichier is None:
            raise RuntimeError("lecteur non ouvert : utiliser with")
        lecteur = csv.DictReader(self.fichier)
        for rec in lecteur:
            verifier(self.chemin.name, lecteur.line_num, rec, self.obligatoires)
            yield rec


class LecteurMemoire:
    """Aucune ressource à libérer, donc pas de with : sert surtout dans les tests."""

    def __init__(self, recs: list[dict[str, str]], obligatoires: Sequence[str] = ()) -> None:
        self.recs = recs
        self.obligatoires = obligatoires

    def enregistrements(self) -> Iterator[dict[str, str]]:
        for i, rec in enumerate(self.recs, start=1):
            verifier("memoire", i, rec, self.obligatoires)
            yield rec


def compter(lecteur: LecteurEnregistrements) -> int:
    return sum(1 for _ in lecteur.enregistrements())


def compter_tous(chemins: Sequence[Path]) -> int:
    """Ouvre tous les fichiers en même temps ; si l'un échoue, les précédents sont fermés."""
    with ExitStack() as pile:
        lecteurs = [pile.enter_context(LecteurCSV(c)) for c in chemins]
        return sum(compter(lecteur) for lecteur in lecteurs)
