"""Décorateurs réutilisables du projet."""

from __future__ import annotations

import functools
import logging
import time
import tracemalloc
from collections.abc import Callable, Iterable, Iterator
from typing import ParamSpec, TypeVar

from mobilis.journal import Journal, LigneRejetee

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")
L = TypeVar("L")

journal_log = logging.getLogger("mobilis")


def mesure(libelle: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Journalise la durée d'un appel et, si tracemalloc tourne, son pic mémoire.

    Sur une fonction génératrice, on ne mesurerait que la création du
    générateur : décorer la fonction qui le consomme.
    """

    def decorateur(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def enveloppe(*args: P.args, **kwargs: P.kwargs) -> R:
            memoire = tracemalloc.is_tracing()
            if memoire:
                tracemalloc.reset_peak()
            debut = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                duree = time.perf_counter() - debut
                if memoire:
                    pic = tracemalloc.get_traced_memory()[1] / 1024
                    journal_log.info("%s : %.2f s, pic mémoire %.0f Kio", libelle, duree, pic)
                else:
                    journal_log.info("%s : %.2f s", libelle, duree)

        return enveloppe

    return decorateur


def tolerante(
    convertir: Callable[[L, Journal], T],
) -> Callable[[Iterable[tuple[int, L]], Journal], Iterator[T]]:
    """Fait d'un convertisseur de ligne une étape de pipeline qui ne s'arrête pas.

    Le convertisseur reçoit le journal pour y noter ses corrections. Une ligne
    qui lève LigneRejetee est écartée et notée avec son numéro ; les autres
    exceptions remontent (ce sont des bugs).
    """

    @functools.wraps(convertir)
    def etape(lignes: Iterable[tuple[int, L]], journal: Journal) -> Iterator[T]:
        for numero, ligne in lignes:
            try:
                yield convertir(ligne, journal)
            except LigneRejetee as e:
                journal.noter(e.type, f"ligne {numero} : {e.detail}")

    return etape
