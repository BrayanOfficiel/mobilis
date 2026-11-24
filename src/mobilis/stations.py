"""Référentiel des stations : lecture, normalisation et validation de stations.csv."""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from mobilis.journal import LigneRejetee

# Export de l'ancien outil Windows.
ENCODAGE = "cp1252"
COLONNES = (
    "Code station",
    "Nom",
    "Commune",
    "Capacité",
    "Latitude",
    "Longitude",
    "Statut",
    "Mise en service",
)
MOTIF_CODE = re.compile(r"MB-\d{4}")

# Emprise large de l'agglomération, sert seulement à repérer les coordonnées
# inversées : (4.79, 45.73) est un point valide sur Terre, mais pas chez nous.
LATITUDES = (44.0, 47.0)
LONGITUDES = (3.0, 6.0)


class Statut(Enum):
    EN_SERVICE = "en service"
    HORS_SERVICE = "hors service"
    FERMEE = "fermée"

    @classmethod
    def depuis_texte(cls, texte: str) -> Statut:
        """Normalise les graphies de l'export ("EN SERVICE", "en_service", "HS"...)."""
        cle = " ".join(texte.replace("_", " ").split()).lower()
        try:
            return _ALIAS_STATUTS[cle]
        except KeyError:
            raise ValueError(f"statut inconnu : {texte!r}") from None


_ALIAS_STATUTS = {
    "en service": Statut.EN_SERVICE,
    "hors service": Statut.HORS_SERVICE,
    "hs": Statut.HORS_SERVICE,
    "fermee": Statut.FERMEE,
    "fermée": Statut.FERMEE,
}


@dataclass(frozen=True, slots=True)
class Station:
    code: str
    nom: str
    commune: str
    capacite: int
    latitude: float
    longitude: float
    statut: Statut
    mise_en_service: date

    def __post_init__(self) -> None:
        if not MOTIF_CODE.fullmatch(self.code):
            raise ValueError(f"code station invalide : {self.code!r}")
        if not self.nom or not self.commune:
            raise ValueError("nom et commune sont obligatoires")
        if self.capacite <= 0:
            raise ValueError(f"capacité invalide : {self.capacite}")
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError(f"coordonnées invalides : {self.latitude}, {self.longitude}")

    @property
    def exploitable(self) -> bool:
        return self.statut is Statut.EN_SERVICE


class TypeAnomalie(Enum):
    ESPACES = "espaces en trop autour d'un champ"
    DATE_ISO = "date au format AAAA-MM-JJ"
    COORDONNEES_INVERSEES = "latitude et longitude inversées"
    NB_COLONNES = "nombre de colonnes incorrect"
    CAPACITE_INVALIDE = "capacité absente ou non numérique"
    COORDONNEES_INVALIDES = "coordonnées absentes ou hors zone"
    DATE_INVALIDE = "date de mise en service illisible"
    STATUT_INCONNU = "statut inconnu"
    VALEUR_INVALIDE = "valeur refusée par la validation"
    DOUBLON = "code station en double"


# Anomalies que l'on sait corriger sans inventer d'information ; les autres
# font écarter la ligne.
CORRIGEABLES = frozenset(
    {TypeAnomalie.ESPACES, TypeAnomalie.DATE_ISO, TypeAnomalie.COORDONNEES_INVERSEES}
)


@dataclass(frozen=True, slots=True)
class Anomalie:
    ligne: int
    code: str
    type: TypeAnomalie
    detail: str = ""

    @property
    def ecartee(self) -> bool:
        return self.type not in CORRIGEABLES


@dataclass
class RapportStations:
    lignes_lues: int = 0
    stations: list[Station] = field(default_factory=list)
    codes_lus: set[str] = field(default_factory=set)
    anomalies: list[Anomalie] = field(default_factory=list)

    @property
    def exploitables(self) -> list[Station]:
        return [s for s in self.stations if s.exploitable]

    @property
    def lignes_ecartees(self) -> int:
        return len({a.ligne for a in self.anomalies if a.ecartee})

    def par_type(self) -> Counter[TypeAnomalie]:
        return Counter(a.type for a in self.anomalies)

    def par_statut(self) -> Counter[Statut]:
        return Counter(s.statut for s in self.stations)


def lire_lignes(chemin: Path) -> Iterator[tuple[int, list[str]]]:
    """Produit (numéro de ligne, champs) pour chaque ligne de données."""
    with chemin.open(encoding=ENCODAGE, newline="") as f:
        lecteur = csv.reader(f, delimiter=";")
        entete = next(lecteur, None)
        if entete is None or tuple(c.strip() for c in entete) != COLONNES:
            raise ValueError(f"{chemin} : en-tête inattendu {entete!r}")
        for champs in lecteur:
            if champs:
                yield lecteur.line_num, champs


def _decimal(texte: str) -> float:
    return float(texte.replace(",", "."))


def _dans_la_zone(lat: float, lon: float) -> bool:
    return LATITUDES[0] <= lat <= LATITUDES[1] and LONGITUDES[0] <= lon <= LONGITUDES[1]


def _lire_date(texte: str, ligne: int, code: str) -> tuple[date, list[Anomalie]]:
    try:
        return datetime.strptime(texte, "%d/%m/%Y").date(), []
    except ValueError:
        pass
    try:
        valeur = date.fromisoformat(texte)
    except ValueError:
        raise LigneRejetee(TypeAnomalie.DATE_INVALIDE, texte) from None
    return valeur, [Anomalie(ligne, code, TypeAnomalie.DATE_ISO, texte)]


def _lire_coordonnees(
    lat_txt: str, lon_txt: str, ligne: int, code: str
) -> tuple[float, float, list[Anomalie]]:
    try:
        lat, lon = _decimal(lat_txt), _decimal(lon_txt)
    except ValueError:
        raise LigneRejetee(
            TypeAnomalie.COORDONNEES_INVALIDES, f"{lat_txt!r}, {lon_txt!r}"
        ) from None
    if _dans_la_zone(lat, lon):
        return lat, lon, []
    if _dans_la_zone(lon, lat):
        anomalie = Anomalie(ligne, code, TypeAnomalie.COORDONNEES_INVERSEES, f"{lat}, {lon}")
        return lon, lat, [anomalie]
    raise LigneRejetee(TypeAnomalie.COORDONNEES_INVALIDES, f"{lat}, {lon}")


def lire_station(ligne: int, champs: list[str]) -> tuple[Station, list[Anomalie]]:
    """Construit une Station à partir d'une ligne brute.

    Renvoie aussi les corrections appliquées ; lève LigneRejetee si la ligne
    est inutilisable.
    """
    if len(champs) != len(COLONNES):
        raise LigneRejetee(TypeAnomalie.NB_COLONNES, f"{len(champs)} colonnes")
    nettoyes = [c.strip() for c in champs]
    code, nom, commune, capacite, lat, lon, statut, mise_en_service = nettoyes
    corrections: list[Anomalie] = []
    if nettoyes != champs:
        corrections.append(Anomalie(ligne, code, TypeAnomalie.ESPACES))

    if not capacite.isdigit():
        raise LigneRejetee(TypeAnomalie.CAPACITE_INVALIDE, repr(capacite))
    latitude, longitude, inversion = _lire_coordonnees(lat, lon, ligne, code)
    jour, format_date = _lire_date(mise_en_service, ligne, code)
    try:
        statut_normalise = Statut.depuis_texte(statut)
    except ValueError as e:
        raise LigneRejetee(TypeAnomalie.STATUT_INCONNU, str(e)) from None

    try:
        station = Station(
            code=code,
            nom=nom,
            commune=commune,
            capacite=int(capacite),
            latitude=latitude,
            longitude=longitude,
            statut=statut_normalise,
            mise_en_service=jour,
        )
    except ValueError as e:
        raise LigneRejetee(TypeAnomalie.VALEUR_INVALIDE, str(e)) from None
    return station, corrections + inversion + format_date


def lire_stations(chemin: Path) -> RapportStations:
    """Lit stations.csv sans s'arrêter à la première erreur.

    Les lignes inutilisables sont écartées et consignées dans le rapport. Pour
    un code présent plusieurs fois, on garde la mise en service la plus
    récente : les doublons de l'export sont des remises en service après
    travaux (nouvelle capacité).
    """
    rapport = RapportStations()
    retenues: dict[str, tuple[int, Station]] = {}
    for ligne, champs in lire_lignes(chemin):
        rapport.lignes_lues += 1
        code = champs[0].strip() if champs else ""
        if code:
            rapport.codes_lus.add(code)
        try:
            station, corrections = lire_station(ligne, champs)
        except LigneRejetee as e:
            rapport.anomalies.append(Anomalie(ligne, code, e.type, e.detail))
            continue
        rapport.anomalies.extend(corrections)

        precedente = retenues.get(station.code)
        if precedente is None:
            retenues[station.code] = (ligne, station)
            continue
        ligne_prec, station_prec = precedente
        if station.mise_en_service >= station_prec.mise_en_service:
            retenues[station.code] = (ligne, station)
            ligne_ecartee, gardee = ligne_prec, ligne
        else:
            ligne_ecartee, gardee = ligne, ligne_prec
        rapport.anomalies.append(
            Anomalie(ligne_ecartee, station.code, TypeAnomalie.DOUBLON, f"ligne {gardee} retenue")
        )

    rapport.stations = sorted((s for _, s in retenues.values()), key=lambda s: s.code)
    rapport.anomalies.sort(key=lambda a: a.ligne)
    return rapport
