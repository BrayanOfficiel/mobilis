"""Benchmark du cours : séquentiel, threads et asyncio pour des attentes simulées."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor


def tache_io(n: int) -> int:
    time.sleep(0.1)
    return n * n


async def tache_async(n: int) -> int:
    await asyncio.sleep(0.1)
    return n * n


def sequentiel(items: list[int]) -> list[int]:
    return [tache_io(n) for n in items]


def avec_threads(items: list[int], workers: int = 10) -> list[int]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(tache_io, items))


async def avec_asyncio(items: list[int]) -> list[int]:
    return list(await asyncio.gather(*(tache_async(n) for n in items)))


if __name__ == "__main__":
    items = list(range(10))
    attendu = sequentiel(items)
    for nom, fn in (
        ("séquentiel", sequentiel),
        ("threads", avec_threads),
        ("asyncio", lambda xs: asyncio.run(avec_asyncio(xs))),
    ):
        debut = time.perf_counter()
        assert fn(items) == attendu
        print(f"{nom:<11}: {time.perf_counter() - debut:.2f} s")
