"""Benchmark du cours : une tâche de calcul, threads contre processus."""

from __future__ import annotations

import time
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor


def tache_cpu(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total


def mesurer(pool: Executor, items: list[int]) -> float:
    debut = time.perf_counter()
    list(pool.map(tache_cpu, items))
    return time.perf_counter() - debut


if __name__ == "__main__":
    items = [3_000_000] * 4
    debut = time.perf_counter()
    [tache_cpu(n) for n in items]
    print(f"séquentiel        : {time.perf_counter() - debut:.2f} s")
    with ThreadPoolExecutor(max_workers=4) as threads:
        print(f"threads (GIL)     : {mesurer(threads, items):.2f} s")
    # Mesure à froid : le démarrage des processus est compté, c'est ce que paie l'utilisateur.
    debut = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as processus:
        chaud = mesurer(processus, items)
    print(f"processus (chaud) : {chaud:.2f} s")
    print(f"processus (froid) : {time.perf_counter() - debut:.2f} s")
