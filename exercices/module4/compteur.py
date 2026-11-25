"""Exercice 6 du module 4 : le GIL ne rend pas `compteur += 1` atomique."""

from __future__ import annotations

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


class Compteur:
    def __init__(self) -> None:
        self.valeur = 0
        self.verrou = threading.Lock()

    def incrementer_sans_verrou(self, n: int) -> None:
        for _ in range(n):
            v = self.valeur
            # Lire puis écrire en deux temps : un autre thread peut passer entre les deux.
            # sleep(0) force ce changement de thread pour rendre la course visible à coup sûr.
            time.sleep(0)
            self.valeur = v + 1

    def incrementer(self, n: int) -> None:
        for _ in range(n):
            with self.verrou:
                self.valeur += 1


def compter_par_resultats(morceaux: list[list[str]]) -> Counter[str]:
    """Sans état partagé : chaque thread renvoie son Counter, le thread principal fusionne."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        partiels: list[Counter[str]] = list(pool.map(Counter, morceaux))
    return sum(partiels, Counter())


if __name__ == "__main__":
    for methode in ("incrementer_sans_verrou", "incrementer"):
        c = Compteur()
        threads = [threading.Thread(target=getattr(c, methode), args=(20_000,)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print(f"{methode:<24} {c.valeur} (attendu 200000)")
