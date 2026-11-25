"""Cas 4 sans serveur : l'API est remplacée par des mocks."""

import asyncio
import io
import json
import urllib.error
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import date
from email.message import Message
from unittest import mock

import pytest

from mobilis.bornes import (
    ClientBornes,
    ClientBornesAsync,
    ErreurApi,
    EtatStation,
    Photo,
    SourceBornes,
    comparer,
    photographier_asyncio,
    photographier_sequentiel,
    photographier_threads,
    reessayer,
    reessayer_async,
)
from mobilis.stations import RapportStations, Station, Statut


def etat_json(code: str, meca: int = 3, elec: int = 1, places: int = 6) -> dict[str, object]:
    return {
        "code": code,
        "velos_mecaniques": meca,
        "velos_electriques": elec,
        "places_libres": places,
        "horodatage": "2026-11-25T08:00:00+00:00",
    }


class Appels:
    """Fonction qui lève les erreurs prévues puis renvoie "ok"."""

    __name__ = "appel"

    def __init__(self, *erreurs: ErreurApi) -> None:
        self.erreurs = list(erreurs)
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        if self.erreurs:
            raise self.erreurs.pop(0)
        return "ok"


def test_reessai_puis_succes_avec_attente_croissante() -> None:
    attentes: list[float] = []
    appel = Appels(ErreurApi(503, "indisponible"), ErreurApi(504, "borne"))
    assert reessayer(dormir=attentes.append)(appel)() == "ok"
    assert appel.n == 3
    assert attentes == [0.2, 0.4]


def test_retry_after_respecte() -> None:
    attentes: list[float] = []
    appel = Appels(ErreurApi(429, "trop", attente=1.0))
    reessayer(dormir=attentes.append)(appel)()
    assert attentes == [1.0]


@pytest.mark.parametrize("statut", [400, 401, 404])
def test_pas_de_reessai_sur_erreur_definitive(statut: int) -> None:
    appel = Appels(ErreurApi(statut, "non"))
    with pytest.raises(ErreurApi):
        reessayer(dormir=lambda _: None)(appel)()
    assert appel.n == 1


def test_abandon_apres_le_dernier_essai() -> None:
    attentes: list[float] = []
    appel = Appels(*[ErreurApi(504, "borne")] * 10)
    with pytest.raises(ErreurApi, match="504"):
        reessayer(essais=4, dormir=attentes.append)(appel)()
    assert appel.n == 4 and len(attentes) == 3


def test_reessai_async() -> None:
    attentes: list[float] = []

    async def dormir(s: float) -> None:
        attentes.append(s)

    appel = Appels(ErreurApi(None, "réseau"))

    @reessayer_async(dormir=dormir)
    async def lire() -> str:
        return appel()

    assert asyncio.run(lire()) == "ok"
    assert attentes == [0.2]


class FausseReponse(io.BytesIO):
    status = 200


def erreur_http(statut: int, corps: dict[str, str], retry_after: str | None = None) -> Exception:
    entetes = Message()
    if retry_after:
        entetes["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        "http://api", statut, "", entetes, io.BytesIO(json.dumps(corps).encode())
    )


def test_client_pagination_et_reessai() -> None:
    reponses = [
        FausseReponse(json.dumps({"page": 1, "stations": ["A"], "page_suivante": 2}).encode()),
        erreur_http(503, {"erreur": "indisponible"}),
        FausseReponse(json.dumps({"page": 2, "stations": ["B"], "page_suivante": None}).encode()),
        FausseReponse(json.dumps(etat_json("A")).encode()),
    ]
    with (
        mock.patch("urllib.request.urlopen", side_effect=reponses) as urlopen,
        mock.patch("mobilis.bornes.time.sleep") as dormir,
    ):
        client = ClientBornes("http://api/", "cle")
        assert list(client.pages()) == [["A"], ["B"]]
        assert client.etat("A").velos == 4
    requete = urlopen.call_args_list[0].args[0]
    assert requete.full_url == "http://api/stations?page=1"
    assert requete.get_header("X-api-key") == "cle"
    dormir.assert_called_once_with(0.2)


def test_client_retry_after_lu_dans_l_entete() -> None:
    with (
        mock.patch(
            "urllib.request.urlopen",
            side_effect=[erreur_http(429, {}, "1"), erreur_http(404, {"erreur": "inconnue"})],
        ),
        mock.patch("mobilis.bornes.time.sleep") as dormir,
        pytest.raises(ErreurApi, match="404 inconnue"),
    ):
        ClientBornes("http://api", "cle").etat("ZZ")
    dormir.assert_called_once_with(1.0)


def connexion(reponse: bytes) -> tuple[asyncio.StreamReader, mock.MagicMock]:
    lecteur = asyncio.StreamReader()
    lecteur.feed_data(reponse)
    lecteur.feed_eof()
    ecrivain = mock.MagicMock()
    ecrivain.drain = mock.AsyncMock()
    ecrivain.wait_closed = mock.AsyncMock()
    return lecteur, ecrivain


def test_client_async_lit_la_reponse_http() -> None:
    corps = json.dumps(etat_json("MB-0001")).encode()

    async def scenario() -> EtatStation:
        connexions = [
            connexion(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + corps)
        ]
        with mock.patch("asyncio.open_connection", side_effect=connexions) as ouvrir:
            etat = await ClientBornesAsync("http://127.0.0.1:8765", "cle").etat("MB-0001")
        ouvrir.assert_called_once_with("127.0.0.1", 8765)
        envoye = connexions[0][1].write.call_args.args[0]
        assert envoye.startswith(b"GET /stations/MB-0001 HTTP/1.0\r\n")
        assert b"X-Api-Key: cle\r\n" in envoye
        return etat

    assert asyncio.run(scenario()).places_libres == 6


def test_client_async_erreur_definitive() -> None:
    async def scenario() -> None:
        reponse = b'HTTP/1.0 404 Not Found\r\n\r\n{"erreur": "station inconnue : X"}'
        with mock.patch("asyncio.open_connection", side_effect=[connexion(reponse)]):
            await ClientBornesAsync("http://127.0.0.1:8765", "cle").etat("X")

    with pytest.raises(ErreurApi, match="404 station inconnue"):
        asyncio.run(scenario())


class FausseSource:
    """Deux pages ; la station B est une borne en panne."""

    def pages(self) -> Iterator[list[str]]:
        yield ["A", "B"]
        yield ["C"]

    def etat(self, code: str) -> EtatStation:
        if code == "B":
            raise ErreurApi(504, "borne injoignable")
        places = 0 if code == "C" else 6
        return EtatStation.depuis_json(etat_json(code, meca=0, elec=0, places=places))


class FausseSourceAsync:
    async def pages(self) -> AsyncIterator[list[str]]:
        for lot in FausseSource().pages():
            yield lot

    async def etat(self, code: str) -> EtatStation:
        await asyncio.sleep(0)
        return FausseSource().etat(code)


def verifier_photo(photo: Photo) -> None:
    assert photo.codes == {"A", "B", "C"}
    assert sorted(photo.etats) == ["A", "C"]
    assert photo.injoignables == {"B": "504 borne injoignable"}
    assert [e.code for e in photo.vides] == ["A", "C"]
    assert [e.code for e in photo.pleines] == ["C"]


@pytest.mark.parametrize("photographier", [photographier_sequentiel, photographier_threads])
def test_photo_une_borne_en_panne_n_arrete_rien(
    photographier: Callable[[SourceBornes], Photo],
) -> None:
    verifier_photo(photographier(FausseSource()))


def test_photo_asyncio() -> None:
    verifier_photo(asyncio.run(photographier_asyncio(FausseSourceAsync())))


def station(code: str, capacite: int, statut: Statut = Statut.EN_SERVICE) -> Station:
    return Station(code, "Nom", "Ville", capacite, 45.7, 4.8, statut, date(2020, 1, 1))


def test_comparer_avec_le_referentiel() -> None:
    photo = Photo()
    photo.ajouter("MB-0001", EtatStation.depuis_json(etat_json("MB-0001", 3, 1, 6)))
    photo.ajouter("MB-0002", EtatStation.depuis_json(etat_json("MB-0002", 3, 1, 8)))
    photo.ajouter("MB-0003", EtatStation.depuis_json(etat_json("MB-0003")))
    photo.ajouter("MB-0151", EtatStation.depuis_json(etat_json("MB-0151")))
    photo.ajouter("MB-0028", ErreurApi(504, "borne"))
    rapport = RapportStations(
        stations=[
            station("MB-0001", 10),
            station("MB-0002", 10),
            station("MB-0003", 10, Statut.FERMEE),
            station("MB-0004", 10),
        ],
        codes_lus={"MB-0001", "MB-0002", "MB-0003", "MB-0004", "MB-0028"},
    )
    ecarts = comparer(photo, rapport)
    assert ecarts.absentes_api == ["MB-0004"]
    assert ecarts.inconnues_referentiel == ["MB-0151"]
    assert ecarts.ecartees_referentiel == ["MB-0028"]
    assert ecarts.capacites == [("MB-0002", 10, 12)]
    assert ecarts.non_exploitables_actives == ["MB-0003"]
