"""Exercice 2 du module 4 : appliquer un traitement CPU à des fichiers sur tous les cœurs."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def analyser(fichier: Path) -> str:
    # Fonction au niveau du module : elle doit pouvoir être envoyée aux processus (pickle).
    return hashlib.sha256(fichier.read_bytes()).hexdigest()


def analyser_tous(fichiers: Iterable[Path], workers: int | None = None) -> dict[Path, str]:
    resultats: dict[Path, str] = {}
    erreurs: dict[Path, str] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futurs = {pool.submit(analyser, f): f for f in fichiers}
        for futur in as_completed(futurs):
            fichier = futurs[futur]
            try:
                resultats[fichier] = futur.result()
            except OSError as e:
                erreurs[fichier] = type(e).__name__
    if erreurs:
        raise RuntimeError(f"{len(erreurs)} fichier(s) en erreur : {erreurs}")
    return resultats


if __name__ == "__main__":
    print(analyser_tous(sorted(Path(".").glob("*.py"))))
