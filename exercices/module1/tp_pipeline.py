"""TP module 1 : pipeline de traitement des ventes par générateurs."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Vente:
    produit: str
    quantite: int
    prix_unitaire: Decimal

    @property
    def montant(self) -> Decimal:
        return self.quantite * self.prix_unitaire


def lire_ventes(chemin: Path) -> Iterator[Vente]:
    """Produit les ventes du fichier une par une."""
    with chemin.open(encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            yield Vente(
                produit=ligne["produit"],
                quantite=int(ligne["quantite"]),
                prix_unitaire=Decimal(ligne["prix_unitaire"]),
            )


def filtrer(ventes: Iterable[Vente], montant_min: Decimal) -> Iterator[Vente]:
    return (v for v in ventes if v.montant >= montant_min)


def total_par_produit(ventes: Iterable[Vente]) -> dict[str, Decimal]:
    totaux: defaultdict[str, Decimal] = defaultdict(Decimal)
    for vente in ventes:
        totaux[vente.produit] += vente.montant
    return dict(totaux)


def main() -> None:
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("ventes.csv")
    ventes = lire_ventes(chemin)
    grosses = filtrer(ventes, Decimal("20"))
    # Rien n'a encore été lu : le fichier n'est ouvert qu'au premier next().
    print(type(ventes).__name__, type(grosses).__name__)
    for produit, total in sorted(total_par_produit(grosses).items()):
        print(f"{produit:<10} {total:>8}")


if __name__ == "__main__":
    main()
