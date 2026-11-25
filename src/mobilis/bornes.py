"""État du réseau en temps réel (cas 4) : client de l'API des bornes.

L'API est lente, renvoie parfois 503 ou 504, et refuse (429) au-delà de 8
requêtes simultanées. Trois façons de photographier toutes les stations sont
gardées pour la comparaison : séquentielle, threads, asyncio.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ParamSpec, Protocol, TypeVar
from urllib.parse import urlsplit

from mobilis.stations import RapportStations

P = ParamSpec("P")
R = TypeVar("R")

MAX_SIMULTANES = 8
REESSAYABLES = frozenset({429, 503, 504})
journal = logging.getLogger("mobilis")


class ErreurApi(Exception):
    """Réponse en erreur ; `statut` vaut None pour une erreur réseau (connexion, délai)."""

    def __init__(self, statut: int | None, message: str, attente: float | None = None) -> None:
        super().__init__(f"{statut} {message}" if statut else message)
        self.statut = statut
        self.attente = attente

    @property
    def reessayable(self) -> bool:
        return self.statut is None or self.statut in REESSAYABLES


def delai_avant(erreur: ErreurApi, essai: int, base: float) -> float:
    """Le Retry-After du serveur s'il y en a un, sinon une attente qui double à chaque essai."""
    return erreur.attente if erreur.attente is not None else base * 2**essai


def reessayer(
    essais: int = 4, base: float = 0.2, dormir: Callable[[float], None] | None = None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Réessaie un appel en cas de 429, 503, 504 ou d'erreur réseau, au plus `essais` fois.

    `dormir` remplace `time.sleep` dans les tests.
    """

    def decorateur(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def enveloppe(*args: P.args, **kwargs: P.kwargs) -> R:
            for essai in range(essais):
                try:
                    return fn(*args, **kwargs)
                except ErreurApi as e:
                    if not e.reessayable or essai == essais - 1:
                        raise
                    journal.debug("%s : %s, nouvel essai", fn.__name__, e)
                    (dormir or time.sleep)(delai_avant(e, essai, base))
            raise AssertionError("inatteignable")

        return enveloppe

    return decorateur


def reessayer_async(
    essais: int = 4,
    base: float = 0.2,
    dormir: Callable[[float], Awaitable[None]] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Même politique que `reessayer`, pour une coroutine : l'attente ne bloque pas la boucle."""

    def decorateur(fn: Callable[P, Awaitable[R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(fn)
        async def enveloppe(*args: P.args, **kwargs: P.kwargs) -> R:
            for essai in range(essais):
                try:
                    return await fn(*args, **kwargs)
                except ErreurApi as e:
                    if not e.reessayable or essai == essais - 1:
                        raise
                    journal.debug("%s : %s, nouvel essai", fn.__name__, e)
                    await (dormir or asyncio.sleep)(delai_avant(e, essai, base))
            raise AssertionError("inatteignable")

        return enveloppe

    return decorateur


def decoder_reponse(statut: int, retry_after: str | None, corps: bytes) -> Any:
    if statut == 200:
        return json.loads(corps)
    try:
        message = json.loads(corps).get("erreur", "")
    except (ValueError, AttributeError):
        message = corps[:100].decode("utf-8", "replace")
    attente = float(retry_after) if retry_after else None
    raise ErreurApi(statut, message, attente)


@dataclass(frozen=True, slots=True)
class EtatStation:
    code: str
    velos_mecaniques: int
    velos_electriques: int
    places_libres: int
    horodatage: datetime

    @classmethod
    def depuis_json(cls, d: dict[str, Any]) -> EtatStation:
        return cls(
            code=d["code"],
            velos_mecaniques=int(d["velos_mecaniques"]),
            velos_electriques=int(d["velos_electriques"]),
            places_libres=int(d["places_libres"]),
            horodatage=datetime.fromisoformat(d["horodatage"]),
        )

    @property
    def velos(self) -> int:
        return self.velos_mecaniques + self.velos_electriques

    @property
    def capacite(self) -> int:
        return self.velos + self.places_libres

    @property
    def vide(self) -> bool:
        return self.velos == 0

    @property
    def pleine(self) -> bool:
        return self.places_libres == 0


class ClientBornes:
    """Client synchrone (urllib), utilisable depuis plusieurs threads.

    Le sémaphore borne les requêtes en vol pour tout le client (pagination
    comprise), pas les attentes entre deux essais.
    """

    def __init__(self, url: str, cle: str, delai: float = 10.0) -> None:
        self.url = url.rstrip("/")
        self.cle = cle
        self.delai = delai
        self.limite = threading.BoundedSemaphore(MAX_SIMULTANES)

    @reessayer()
    def lire(self, chemin: str) -> Any:
        requete = urllib.request.Request(self.url + chemin, headers={"X-Api-Key": self.cle})
        try:
            with self.limite, urllib.request.urlopen(requete, timeout=self.delai) as reponse:
                return decoder_reponse(reponse.status, None, reponse.read())
        except urllib.error.HTTPError as e:
            return decoder_reponse(e.code, e.headers.get("Retry-After"), e.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ErreurApi(None, f"réseau : {e}") from e

    def pages(self) -> Iterator[list[str]]:
        """Les codes des stations, page par page : on peut commencer avant la dernière."""
        page: int | None = 1
        while page is not None:
            lot = self.lire(f"/stations?page={page}")
            yield lot["stations"]
            page = lot["page_suivante"]

    def etat(self, code: str) -> EtatStation:
        return EtatStation.depuis_json(self.lire(f"/stations/{code}"))


class ClientBornesAsync:
    """Client asyncio écrit sur `open_connection` : la bibliothèque standard n'a pas de
    client HTTP asynchrone. Le sémaphore borne les requêtes en vol, pas les attentes
    entre deux essais."""

    def __init__(self, url: str, cle: str, delai: float = 10.0) -> None:
        morceaux = urlsplit(url)
        self.hote = morceaux.hostname or "127.0.0.1"
        self.port = morceaux.port or 80
        self.cle = cle
        self.delai = delai
        self.limite = asyncio.Semaphore(MAX_SIMULTANES)

    async def requete(self, chemin: str) -> tuple[int, str | None, bytes]:
        async with self.limite, asyncio.timeout(self.delai):
            lecteur, ecrivain = await asyncio.open_connection(self.hote, self.port)
            try:
                ecrivain.write(
                    f"GET {chemin} HTTP/1.0\r\nHost: {self.hote}\r\n"
                    f"X-Api-Key: {self.cle}\r\n\r\n".encode()
                )
                await ecrivain.drain()
                # HTTP/1.0 : le serveur ferme la connexion après la réponse.
                brut = await lecteur.read()
            finally:
                ecrivain.close()
                await ecrivain.wait_closed()
        tete, _, corps = brut.partition(b"\r\n\r\n")
        lignes = tete.decode("iso-8859-1").split("\r\n")
        statut = int(lignes[0].split()[1])
        entetes = dict(ligne.split(":", 1) for ligne in lignes[1:] if ":" in ligne)
        retry_after = next(
            (v.strip() for k, v in entetes.items() if k.lower() == "retry-after"), None
        )
        return statut, retry_after, corps

    @reessayer_async()
    async def lire(self, chemin: str) -> Any:
        try:
            statut, retry_after, corps = await self.requete(chemin)
        except (OSError, TimeoutError) as e:
            raise ErreurApi(None, f"réseau : {e!r}") from e
        return decoder_reponse(statut, retry_after, corps)

    async def pages(self) -> AsyncIterator[list[str]]:
        page: int | None = 1
        while page is not None:
            lot = await self.lire(f"/stations?page={page}")
            yield lot["stations"]
            page = lot["page_suivante"]

    async def etat(self, code: str) -> EtatStation:
        return EtatStation.depuis_json(await self.lire(f"/stations/{code}"))


class SourceBornes(Protocol):
    """Ce dont la photographie a besoin ; un faux client suffit dans les tests."""

    def pages(self) -> Iterator[list[str]]: ...

    def etat(self, code: str) -> EtatStation: ...


class SourceBornesAsync(Protocol):
    def pages(self) -> AsyncIterator[list[str]]: ...

    async def etat(self, code: str) -> EtatStation: ...


@dataclass
class Photo:
    """L'état de toutes les stations à un instant, et celles qui n'ont pas répondu."""

    etats: dict[str, EtatStation] = field(default_factory=dict)
    injoignables: dict[str, str] = field(default_factory=dict)

    def ajouter(self, code: str, resultat: EtatStation | ErreurApi) -> None:
        if isinstance(resultat, ErreurApi):
            self.injoignables[code] = str(resultat)
        else:
            self.etats[code] = resultat

    @property
    def codes(self) -> set[str]:
        """Toutes les stations listées par l'API, qu'elles aient répondu ou non."""
        return set(self.etats) | set(self.injoignables)

    @property
    def vides(self) -> list[EtatStation]:
        return sorted((e for e in self.etats.values() if e.vide), key=lambda e: e.code)

    @property
    def pleines(self) -> list[EtatStation]:
        return sorted((e for e in self.etats.values() if e.pleine), key=lambda e: e.code)


def etat_ou_erreur(source: SourceBornes, code: str) -> EtatStation | ErreurApi:
    # Une borne en panne ne doit pas faire échouer la photo des 149 autres.
    try:
        return source.etat(code)
    except ErreurApi as e:
        return e


def photographier_sequentiel(source: SourceBornes) -> Photo:
    photo = Photo()
    for lot in source.pages():
        for code in lot:
            photo.ajouter(code, etat_ou_erreur(source, code))
    return photo


def photographier_threads(source: SourceBornes, workers: int = MAX_SIMULTANES) -> Photo:
    """L'attente réseau relâche le GIL : les threads attendent ensemble.

    Les stations d'une page partent dès que la page est lue, pendant que le
    thread principal demande la suivante.
    """
    futurs: dict[str, Future[EtatStation | ErreurApi]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for lot in source.pages():
            for code in lot:
                futurs[code] = pool.submit(etat_ou_erreur, source, code)
    photo = Photo()
    for code, futur in futurs.items():
        photo.ajouter(code, futur.result())
    return photo


async def photographier_asyncio(source: SourceBornesAsync) -> Photo:
    """Une tâche par station, créée dès que sa page est lue ; le client borne les requêtes."""

    async def etat_ou_erreur_async(code: str) -> EtatStation | ErreurApi:
        try:
            return await source.etat(code)
        except ErreurApi as e:
            return e

    taches: dict[str, asyncio.Task[EtatStation | ErreurApi]] = {}
    async with asyncio.TaskGroup() as groupe:
        async for lot in source.pages():
            for code in lot:
                taches[code] = groupe.create_task(etat_ou_erreur_async(code))
    photo = Photo()
    for code, tache in taches.items():
        photo.ajouter(code, tache.result())
    return photo


@dataclass
class Ecarts:
    """Désaccords entre le système des bornes et le référentiel des stations."""

    absentes_api: list[str]
    inconnues_referentiel: list[str]
    ecartees_referentiel: list[str]
    capacites: list[tuple[str, int, int]]
    non_exploitables_actives: list[str]


def comparer(photo: Photo, rapport: RapportStations) -> Ecarts:
    api = photo.codes
    retenues = {s.code: s for s in rapport.stations}
    capacites = [
        (code, retenues[code].capacite, etat.capacite)
        for code, etat in sorted(photo.etats.items())
        if code in retenues and retenues[code].capacite != etat.capacite
    ]
    return Ecarts(
        absentes_api=sorted(set(retenues) - api),
        inconnues_referentiel=sorted(api - rapport.codes_lus),
        ecartees_referentiel=sorted((api & rapport.codes_lus) - set(retenues)),
        capacites=capacites,
        non_exploitables_actives=sorted(
            code for code in photo.etats if code in retenues and not retenues[code].exploitable
        ),
    )
