"""Facturation des trajets (cas 3) : règles R1 à R9 de la spécification, en Decimal.

R10 à R12 sont déjà appliquées par la chaîne des trajets (`trajets_propres`).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from mobilis.abonnes import Abonnes, Formule
from mobilis.decorateurs import mesure
from mobilis.journal import Journal
from mobilis.trajets import PARIS, Trajet, TypeVelo, trajets_propres

CENTIME = Decimal("0.01")
DUREE_FANTOME = timedelta(minutes=2)


def arrondir(montant: Decimal) -> Decimal:
    """R7 : au centime le plus proche, la moitié vers le haut."""
    return montant.quantize(CENTIME, rounding=ROUND_HALF_UP)


def tranches(duree: timedelta, tranche: timedelta) -> int:
    """Nombre de tranches entamées : une seconde de trop en ouvre une nouvelle."""
    return -(-duree // tranche)


def jour_local(instant: datetime) -> date:
    return instant.astimezone(PARIS).date()


@dataclass(frozen=True, slots=True)
class Bareme:
    """Les tarifs d'une formule dans une grille."""

    minutes_incluses: timedelta
    tranche: timedelta
    prix_tranche: Decimal
    supplement_electrique: Decimal
    frais_deblocage: Decimal
    plafond_jour: Decimal | None

    @classmethod
    def depuis_json(cls, d: Mapping[str, Any]) -> Bareme:
        plafond = d["plafond_jour"]
        return cls(
            minutes_incluses=timedelta(minutes=d["minutes_incluses"]),
            tranche=timedelta(minutes=d["tranche_minutes"]),
            prix_tranche=Decimal(d["prix_tranche"]),
            supplement_electrique=Decimal(d["supplement_electrique_tranche"]),
            frais_deblocage=Decimal(d["frais_deblocage"]),
            plafond_jour=None if plafond is None else Decimal(plafond),
        )


@dataclass(frozen=True, slots=True)
class Grille:
    en_vigueur_du: date
    baremes: Mapping[Formule, Bareme]


@dataclass(frozen=True, slots=True)
class Tarifs:
    penalite_non_restitution: Decimal
    seuil_non_restitution: timedelta
    grilles: tuple[Grille, ...]

    def grille(self, jour: date) -> Grille:
        """R1 : la dernière grille entrée en vigueur au plus tard ce jour-là."""
        en_vigueur = [g for g in self.grilles if g.en_vigueur_du <= jour]
        if not en_vigueur:
            raise ValueError(f"aucune grille en vigueur le {jour}")
        return max(en_vigueur, key=lambda g: g.en_vigueur_du)

    def avant(self, jour: date) -> Tarifs:
        """Les mêmes tarifs sans les grilles entrées en vigueur à partir de `jour`."""
        return replace(self, grilles=tuple(g for g in self.grilles if g.en_vigueur_du < jour))


def lire_tarifs(chemin: Path) -> Tarifs:
    # parse_float : un montant écrit 0.6 sans guillemets ne passe jamais par un float.
    with chemin.open(encoding="utf-8") as f:
        brut = json.load(f, parse_float=Decimal)
    grilles = tuple(
        Grille(
            en_vigueur_du=date.fromisoformat(g["en_vigueur_du"]),
            baremes={Formule(nom): Bareme.depuis_json(b) for nom, b in g["formules"].items()},
        )
        for g in brut["grilles"]
    )
    return Tarifs(
        penalite_non_restitution=Decimal(brut["penalite_non_restitution"]),
        seuil_non_restitution=timedelta(hours=brut["seuil_non_restitution_heures"]),
        grilles=grilles,
    )


class Tarification(ABC):
    """Prix d'un trajet restitué pour une formule.

    Le calcul R4 + R5 est commun ; chaque formule décide comment le plafond
    journalier R6 s'applique.
    """

    def __init__(self, bareme: Bareme) -> None:
        self.bareme = bareme

    def prix_usage(self, duree: timedelta, type_velo: TypeVelo) -> Decimal:
        b = self.bareme
        usage = max(timedelta(0), duree - b.minutes_incluses)
        prix = b.frais_deblocage + tranches(usage, b.tranche) * b.prix_tranche
        if type_velo is TypeVelo.ELECTRIQUE:
            prix += tranches(duree, b.tranche) * b.supplement_electrique
        return prix

    @abstractmethod
    def facturer(self, trajet: Trajet, duree: timedelta) -> Decimal: ...


class TarifOccasionnel(Tarification):
    """Pas de plafond : chaque trajet paie son prix."""

    def facturer(self, trajet: Trajet, duree: timedelta) -> Decimal:
        return arrondir(self.prix_usage(duree, trajet.type_velo))


class TarifAbonnement(Tarification):
    """Plafond par abonné et par jour local : retient ce que chacun a déjà payé."""

    def __init__(self, bareme: Bareme) -> None:
        if bareme.plafond_jour is None:
            raise ValueError("une formule d'abonnement a un plafond journalier")
        super().__init__(bareme)
        self.plafond = bareme.plafond_jour
        # Le fichier n'est pas trié : on ne peut jamais oublier une journée. La taille
        # reste bornée par abonnés x jours, pas par le nombre de trajets.
        self.deja_paye: dict[tuple[str | None, date], Decimal] = {}

    def facturer(self, trajet: Trajet, duree: timedelta) -> Decimal:
        cle = (trajet.abonne_id, jour_local(trajet.debut))
        deja = self.deja_paye.get(cle, Decimal(0))
        montant = min(self.prix_usage(duree, trajet.type_velo), self.plafond - deja)
        self.deja_paye[cle] = deja + montant
        return arrondir(montant)


class AnomalieFacturation(Enum):
    ABONNE_INTROUVABLE = "abonné absent de abonnes.jsonl, tarif occasionnel"
    ABONNEMENT_INACTIF = "abonnement expiré ou pas commencé, tarif occasionnel"
    FANTOME = "trajet fantôme, non facturé"
    NON_RESTITUTION = "vélo non restitué, pénalité"


SIGNALEES = frozenset({AnomalieFacturation.ABONNE_INTROUVABLE, AnomalieFacturation.FANTOME})


@dataclass
class ChiffreAffaires:
    """Montants et nombres de trajets par (mois local, formule)."""

    montants: defaultdict[tuple[str, Formule], Decimal] = field(
        default_factory=lambda: defaultdict(Decimal)
    )
    trajets: Counter[tuple[str, Formule]] = field(default_factory=Counter)
    penalites: defaultdict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))

    def ajouter(self, mois: str, formule: Formule, montant: Decimal, penalite: bool) -> None:
        self.montants[mois, formule] += montant
        self.trajets[mois, formule] += 1
        if penalite:
            self.penalites[mois] += montant

    def mois(self) -> list[str]:
        return sorted({m for m, _ in self.trajets})

    def total(self, mois: str | None = None) -> Decimal:
        return sum(
            (v for (m, _), v in self.montants.items() if mois is None or m == mois), Decimal(0)
        )


class Facturation:
    """Facture les trajets un par un et cumule le chiffre d'affaires."""

    def __init__(self, tarifs: Tarifs, abonnes: Abonnes, journal: Journal) -> None:
        self.tarifs = tarifs
        self.abonnes = abonnes
        self.journal = journal
        self.ca = ChiffreAffaires()
        self.introuvables: set[str] = set()
        self.tarifications: dict[tuple[date, Formule], Tarification] = {
            (g.en_vigueur_du, formule): (
                TarifOccasionnel(b) if formule is Formule.OCCASIONNEL else TarifAbonnement(b)
            )
            for g in tarifs.grilles
            for formule, b in g.baremes.items()
        }

    def formule(self, trajet: Trajet, jour: date) -> Formule:
        """R2 et R3."""
        if trajet.abonne_id is None:
            return Formule.OCCASIONNEL
        if trajet.abonne_id not in self.abonnes:
            self.introuvables.add(trajet.abonne_id)
            self.journal.noter(AnomalieFacturation.ABONNE_INTROUVABLE, trajet.abonne_id)
            return Formule.OCCASIONNEL
        formule = self.abonnes.formule(trajet.abonne_id, jour)
        if formule is None:
            self.journal.noter(AnomalieFacturation.ABONNEMENT_INACTIF, trajet.abonne_id)
            return Formule.OCCASIONNEL
        return formule

    def facturer(self, trajet: Trajet) -> Decimal:
        jour = jour_local(trajet.debut)
        formule = self.formule(trajet, jour)
        duree = trajet.duree
        penalite = duree is None or duree > self.tarifs.seuil_non_restitution
        if duree is None or penalite:
            self.journal.noter(AnomalieFacturation.NON_RESTITUTION, trajet.trajet_id)
            montant = self.tarifs.penalite_non_restitution
        elif duree < DUREE_FANTOME and trajet.station_arrivee == trajet.station_depart:
            self.journal.noter(AnomalieFacturation.FANTOME, trajet.trajet_id)
            montant = Decimal("0.00")
        else:
            grille = self.tarifs.grille(jour)
            montant = self.tarifications[grille.en_vigueur_du, formule].facturer(trajet, duree)
        self.ca.ajouter(jour.strftime("%Y-%m"), formule, montant, penalite)
        return montant

    def facturer_tous(self, trajets: Iterable[Trajet]) -> ChiffreAffaires:
        for trajet in trajets:
            self.facturer(trajet)
        return self.ca


@mesure("facturation")
def facturer_fichier(
    chemin: Path,
    tarifs: Tarifs,
    abonnes: Abonnes,
    journal: Journal,
    codes_connus: Collection[str] | None = None,
    mois: str | None = None,
) -> Facturation:
    """Facture tout le fichier des trajets, nettoyé par la même chaîne que le cas 2."""
    facturation = Facturation(tarifs, abonnes, journal)
    facturation.facturer_tous(trajets_propres(chemin, journal, codes_connus, mois))
    return facturation
