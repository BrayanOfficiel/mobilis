import asyncio
import threading
from pathlib import Path

from analyser import analyser, analyser_tous
from bench_io import avec_asyncio, avec_threads, sequentiel
from compteur import Compteur, compter_par_resultats


def test_memes_resultats_quelle_que_soit_la_strategie() -> None:
    items = [1, 2, 3]
    assert sequentiel(items) == avec_threads(items) == asyncio.run(avec_asyncio(items))


def test_analyser_tous(tmp_path: Path) -> None:
    fichiers = []
    for i in range(3):
        f = tmp_path / f"{i}.txt"
        f.write_text(str(i), encoding="utf-8")
        fichiers.append(f)
    resultats = analyser_tous(fichiers, workers=2)
    assert resultats == {f: analyser(f) for f in fichiers}


def test_compteur_avec_verrou() -> None:
    c = Compteur()
    threads = [threading.Thread(target=c.incrementer, args=(10_000,)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert c.valeur == 40_000


def test_compter_sans_etat_partage() -> None:
    assert compter_par_resultats([["a", "b"], ["a"], []]) == {"a": 2, "b": 1}
