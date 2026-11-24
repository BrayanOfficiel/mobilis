"""Trajets : lecture en flux du fichier compressé et fréquentation des stations.

Chaque étape est un générateur : le fichier n'est jamais chargé en entier, la
mémoire ne dépend que du nombre de stations et de jours.
"""

from __future__ import annotations

import csv
import gzip
from collections import Counter, deque
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

from mobilis.decorateurs import mesure, tolerante
from mobilis.journal import Journal, LigneRejetee

PARIS = ZoneInfo("Europe/Paris")
COLONNES = (
    "trajet_id",
    "abonne_id",
    "velo_id",
    "type_velo",
    "station_depart",
    "debut",
    "station_arrivee",
    "fin",
    "distance_m",
)


class TypeVelo(Enum):
    MECANIQUE = "mecanique"
    ELECTRIQUE = "electrique"


class TypeJour(Enum):
    SEMAINE = "semaine"
    WEEK_END = "week-end"

    @classmethod
    def de(cls, jour: date) -> TypeJour:
        return cls.WEEK_END if jour.weekday() >= 5 else cls.SEMAINE


class AnomalieTrajet(Enum):
    DATE_LOCALE = "date JJ/MM/AAAA sans fuseau, lue en heure de Paris"
    DATE_UTC = "date en UTC (suffixe Z)"
    DISTANCE_ABSENTE = "distance absente"
    SANS_ARRIVEE = "pas de station ni d'heure d'arrivée"
    STATION_INCONNUE = "station absente du référentiel"
    LIGNE_INVALIDE = "ligne illisible"
    DOUBLON = "trajet déjà transmis"
    HORODATAGE_INCOHERENT = "fin antérieure au début"


ECARTEES = frozenset(
    {AnomalieTrajet.LIGNE_INVALIDE, AnomalieTrajet.DOUBLON, AnomalieTrajet.HORODATAGE_INCOHERENT}
)


@dataclass(frozen=True, slots=True)
class Trajet:
    trajet_id: str
    abonne_id: str | None
    velo_id: str
    type_velo: TypeVelo
    station_depart: str
    debut: datetime
    station_arrivee: str | None
    fin: datetime | None
    distance_m: int | None

    def __post_init__(self) -> None:
        if (self.station_arrivee is None) != (self.fin is None):
            raise ValueError("station et heure d'arrivée vont ensemble")
        if self.debut.tzinfo is None or (self.fin is not None and self.fin.tzinfo is None):
            raise ValueError("les instants doivent porter un fuseau")

    @property
    def duree(self) -> timedelta | None:
        return None if self.fin is None else self.fin - self.debut


def lire_instant(texte: str) -> datetime:
    """Convertit les trois formats des bornes en instant avec fuseau.

    "2026-08-01T00:04:23+02:00", "2026-07-31T22:54:42Z" et "01/08/2026 00:42:17"
    (heure locale de Paris, sans fuseau). Pour une heure locale ambiguë (nuit du
    passage à l'heure d'hiver), zoneinfo prend la première, l'heure d'été.
    """
    if "/" in texte:
        return datetime.strptime(texte, "%d/%m/%Y %H:%M:%S").replace(tzinfo=PARIS)
    instant = datetime.fromisoformat(texte)
    if instant.tzinfo is None:
        raise ValueError(f"instant sans fuseau : {texte!r}")
    return instant


def ouvrir(chemin: Path) -> TextIO:
    if chemin.suffix == ".gz":
        return gzip.open(chemin, "rt", encoding="utf-8", newline="")
    return chemin.open(encoding="utf-8", newline="")


def lire_lignes(chemin: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Produit (numéro de ligne, ligne) sans charger le fichier."""
    with ouvrir(chemin) as f:
        lecteur = csv.DictReader(f)
        if tuple(lecteur.fieldnames or ()) != COLONNES:
            raise ValueError(f"{chemin} : en-tête inattendu {lecteur.fieldnames!r}")
        for ligne in lecteur:
            yield lecteur.line_num, ligne


@tolerante
def convertir_trajets(ligne: dict[str, str], journal: Journal) -> Trajet:
    # DictReader complète une ligne trop courte par None et range l'excédent sous la clé None.
    if None in ligne or None in ligne.values():
        raise LigneRejetee(AnomalieTrajet.LIGNE_INVALIDE, "nombre de colonnes incorrect")
    try:
        debut = lire_instant(ligne["debut"])
        fin = lire_instant(ligne["fin"]) if ligne["fin"] else None
        type_velo = TypeVelo(ligne["type_velo"])
        distance = int(ligne["distance_m"]) if ligne["distance_m"] else None
        trajet = Trajet(
            trajet_id=ligne["trajet_id"],
            abonne_id=ligne["abonne_id"] or None,
            velo_id=ligne["velo_id"],
            type_velo=type_velo,
            station_depart=ligne["station_depart"],
            debut=debut,
            station_arrivee=ligne["station_arrivee"] or None,
            fin=fin,
            distance_m=distance,
        )
    except ValueError as e:
        raise LigneRejetee(AnomalieTrajet.LIGNE_INVALIDE, str(e)) from None
    if not trajet.trajet_id or not trajet.station_depart:
        raise LigneRejetee(AnomalieTrajet.LIGNE_INVALIDE, "identifiant ou départ vide")

    for texte in (ligne["debut"], ligne["fin"]):
        if "/" in texte:
            journal.noter(AnomalieTrajet.DATE_LOCALE)
        elif texte.endswith("Z"):
            journal.noter(AnomalieTrajet.DATE_UTC)
    if trajet.fin is None:
        journal.noter(AnomalieTrajet.SANS_ARRIVEE, trajet.trajet_id)
    if trajet.distance_m is None:
        journal.noter(AnomalieTrajet.DISTANCE_ABSENTE)
    return trajet


def dedoublonner(
    trajets: Iterable[Trajet], journal: Journal, fenetre: int = 1000
) -> Iterator[Trajet]:
    """Écarte un trajet_id déjà vu parmi les `fenetre` derniers.

    Mémoire bornée : dans l'export, un doublon suit toujours l'original de près
    (ligne suivante). Un doublon plus éloigné que la fenêtre passerait.
    """
    recents: deque[str] = deque()
    vus: set[str] = set()
    for trajet in trajets:
        if trajet.trajet_id in vus:
            journal.noter(AnomalieTrajet.DOUBLON, trajet.trajet_id)
            continue
        recents.append(trajet.trajet_id)
        vus.add(trajet.trajet_id)
        if len(recents) > fenetre:
            vus.discard(recents.popleft())
        yield trajet


def coherents(trajets: Iterable[Trajet], journal: Journal) -> Iterator[Trajet]:
    """Écarte les trajets dont la fin précède le début (R10)."""
    for trajet in trajets:
        if trajet.fin is not None and trajet.fin < trajet.debut:
            journal.noter(AnomalieTrajet.HORODATAGE_INCOHERENT, trajet.trajet_id)
            continue
        yield trajet


def signaler_inconnues(
    trajets: Iterable[Trajet], codes: Collection[str], journal: Journal
) -> Iterator[Trajet]:
    """Laisse passer tous les trajets, signale ceux qui touchent une station inconnue (R12)."""
    for trajet in trajets:
        for code in (trajet.station_depart, trajet.station_arrivee):
            if code is not None and code not in codes:
                journal.noter(AnomalieTrajet.STATION_INCONNUE, f"{trajet.trajet_id} {code}")
        yield trajet


def du_mois(trajets: Iterable[Trajet], mois: str) -> Iterator[Trajet]:
    """Garde les trajets commencés pendant le mois local `mois` ("AAAA-MM")."""
    return (t for t in trajets if t.debut.astimezone(PARIS).strftime("%Y-%m") == mois)


@dataclass
class Frequentation:
    """Départs et arrivées par (station, type de jour, heure locale)."""

    departs: Counter[tuple[str, TypeJour, int]] = field(default_factory=Counter)
    arrivees: Counter[tuple[str, TypeJour, int]] = field(default_factory=Counter)
    jours: set[date] = field(default_factory=set)
    trajets: int = 0

    def ajouter(self, trajet: Trajet) -> None:
        self.trajets += 1
        debut = trajet.debut.astimezone(PARIS)
        self.jours.add(debut.date())
        self.departs[trajet.station_depart, TypeJour.de(debut.date()), debut.hour] += 1
        if trajet.fin is not None and trajet.station_arrivee is not None:
            fin = trajet.fin.astimezone(PARIS)
            self.arrivees[trajet.station_arrivee, TypeJour.de(fin.date()), fin.hour] += 1

    def nb_jours(self, type_jour: TypeJour) -> int:
        return sum(1 for j in self.jours if TypeJour.de(j) is type_jour)

    def profil_horaire(self, type_jour: TypeJour) -> list[tuple[int, float, float]]:
        """(heure, départs moyens par jour, arrivées moyennes par jour) sur tout le réseau."""
        n = self.nb_jours(type_jour) or 1
        departs: Counter[int] = Counter()
        arrivees: Counter[int] = Counter()
        for (_, tj, heure), nb in self.departs.items():
            if tj is type_jour:
                departs[heure] += nb
        for (_, tj, heure), nb in self.arrivees.items():
            if tj is type_jour:
                arrivees[heure] += nb
        return [(h, departs[h] / n, arrivees[h] / n) for h in range(24)]

    def soldes(self, type_jour: TypeJour, heures: range) -> dict[str, float]:
        """Arrivées moins départs par station et par jour sur la plage `heures`."""
        n = self.nb_jours(type_jour) or 1
        soldes: Counter[str] = Counter()
        for (station, tj, heure), nb in self.arrivees.items():
            if tj is type_jour and heure in heures:
                soldes[station] += nb
        for (station, tj, heure), nb in self.departs.items():
            if tj is type_jour and heure in heures:
                soldes[station] -= nb
        return {station: s / n for station, s in soldes.items()}


MATIN = range(7, 10)
SOIR = range(17, 20)


def stations_qui_se_vident(freq: Frequentation, n: int = 10) -> list[tuple[str, float, float]]:
    """Stations qui perdent des vélos le matin et en regagnent le soir, en semaine.

    Triées de la plus vidée le matin à la moins vidée : (code, solde matin, solde soir).
    """
    matin = freq.soldes(TypeJour.SEMAINE, MATIN)
    soir = freq.soldes(TypeJour.SEMAINE, SOIR)
    candidates = [
        (code, matin[code], soir.get(code, 0.0))
        for code in matin
        if matin[code] < 0 and soir.get(code, 0.0) > 0
    ]
    return sorted(candidates, key=lambda c: c[1])[:n]


@mesure("analyse des trajets")
def analyser_trajets(
    chemin: Path,
    journal: Journal,
    codes_connus: Collection[str] | None = None,
    mois: str | None = None,
) -> Frequentation:
    """Lit le fichier des trajets d'un bout à l'autre et agrège la fréquentation."""
    trajets = coherents(
        dedoublonner(convertir_trajets(lire_lignes(chemin), journal), journal), journal
    )
    if codes_connus is not None:
        trajets = signaler_inconnues(trajets, codes_connus, journal)
    if mois is not None:
        trajets = du_mois(trajets, mois)
    freq = Frequentation()
    for trajet in trajets:
        freq.ajouter(trajet)
    return freq
