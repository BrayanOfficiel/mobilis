"""Périodes d'abonnement (abonnes.jsonl) et formule active à une date (R2)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path

from mobilis.decorateurs import tolerante
from mobilis.journal import Journal, LigneRejetee


class Formule(Enum):
    ANNUEL = "annuel"
    MENSUEL = "mensuel"
    SOLIDAIRE = "solidaire"
    OCCASIONNEL = "occasionnel"


class AnomalieAbonne(Enum):
    LIGNE_VIDE = "ligne vide"
    FORMULE_NORMALISEE = "formule avec majuscules ou espaces"
    TRONQUEE_RECUPEREE = "ligne tronquée, champs utiles complets"
    TRONQUEE = "ligne tronquée, champs utiles perdus"
    LIGNE_INVALIDE = "valeur invalide"


ECARTEES_ABONNES = frozenset(
    {AnomalieAbonne.LIGNE_VIDE, AnomalieAbonne.TRONQUEE, AnomalieAbonne.LIGNE_INVALIDE}
)
CHAMPS_UTILES = ("id", "formule", "debut", "fin")
# Une paire "cle": valeur dont la valeur est complète (chaîne fermée ou null).
PAIRE_COMPLETE = re.compile(r'"(\w+)":\s*("[^"]*"|null)')


@dataclass(frozen=True, slots=True)
class Abonnement:
    abonne_id: str
    formule: Formule
    debut: date
    fin: date | None

    def __post_init__(self) -> None:
        if not self.abonne_id:
            raise ValueError("identifiant vide")
        if self.formule is Formule.OCCASIONNEL:
            raise ValueError("occasionnel n'est pas une formule d'abonnement")
        if self.fin is not None and self.fin < self.debut:
            raise ValueError(f"fin {self.fin} avant le début {self.debut}")

    def actif(self, jour: date) -> bool:
        """R2 : debut <= jour <= fin, une fin vide signifie en cours."""
        return self.debut <= jour and (self.fin is None or jour <= self.fin)


def decoder(texte: str, journal: Journal) -> dict[str, object]:
    """Décode une ligne JSON ; une ligne coupée est gardée si les champs utiles sont entiers."""
    try:
        valeurs = json.loads(texte)
    except json.JSONDecodeError:
        paires = {cle: json.loads(valeur) for cle, valeur in PAIRE_COMPLETE.findall(texte)}
        if not all(cle in paires for cle in CHAMPS_UTILES):
            raise LigneRejetee(AnomalieAbonne.TRONQUEE, str(paires.get("id", ""))) from None
        journal.noter(AnomalieAbonne.TRONQUEE_RECUPEREE, str(paires["id"]))
        return paires
    if not isinstance(valeurs, dict):
        raise LigneRejetee(AnomalieAbonne.LIGNE_INVALIDE, "pas un objet JSON")
    return valeurs


def champ(valeurs: dict[str, object], cle: str) -> str | None:
    valeur = valeurs.get(cle)
    if valeur is not None and not isinstance(valeur, str):
        raise LigneRejetee(AnomalieAbonne.LIGNE_INVALIDE, f"{cle} n'est pas un texte")
    return valeur


@tolerante
def convertir_abonnements(texte: str, journal: Journal) -> Abonnement:
    if not texte.strip():
        raise LigneRejetee(AnomalieAbonne.LIGNE_VIDE)
    valeurs = decoder(texte, journal)
    brute = champ(valeurs, "formule") or ""
    propre = brute.strip().lower()
    if propre != brute:
        journal.noter(AnomalieAbonne.FORMULE_NORMALISEE, repr(brute))
    fin = champ(valeurs, "fin")
    try:
        return Abonnement(
            abonne_id=champ(valeurs, "id") or "",
            formule=Formule(propre),
            debut=date.fromisoformat(champ(valeurs, "debut") or ""),
            fin=date.fromisoformat(fin) if fin else None,
        )
    except ValueError as e:
        raise LigneRejetee(AnomalieAbonne.LIGNE_INVALIDE, str(e)) from None


def lire_lignes(chemin: Path) -> Iterator[tuple[int, str]]:
    with chemin.open(encoding="utf-8") as f:
        yield from enumerate(f, start=1)


class Abonnes:
    """Les périodes de chaque abonné, pour retrouver sa formule à une date donnée."""

    def __init__(self, abonnements: Iterable[Abonnement]) -> None:
        self.periodes: defaultdict[str, list[Abonnement]] = defaultdict(list)
        for a in abonnements:
            self.periodes[a.abonne_id].append(a)

    def __contains__(self, abonne_id: object) -> bool:
        return abonne_id in self.periodes

    def __len__(self) -> int:
        return len(self.periodes)

    def formule(self, abonne_id: str, jour: date) -> Formule | None:
        """Formule active ce jour-là, None si aucune période ne le couvre."""
        actives = [a for a in self.periodes.get(abonne_id, ()) if a.actif(jour)]
        if not actives:
            return None
        # Aucun chevauchement dans le kit ; s'il y en avait, la période la plus récente gagne.
        return max(actives, key=lambda a: a.debut).formule


def lire_abonnes(chemin: Path, journal: Journal) -> Abonnes:
    """Lit abonnes.jsonl sans s'arrêter aux lignes abîmées (comptées dans le journal)."""
    return Abonnes(convertir_abonnements(lire_lignes(chemin), journal))
