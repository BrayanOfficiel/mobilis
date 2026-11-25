"""TP du module 5 : le panier du cours, avec l'article le plus cher."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Article:
    nom: str
    prix: float
    quantite: int = 1

    def total(self) -> float:
        return self.prix * self.quantite


@dataclass
class Panier:
    articles: list[Article] = field(default_factory=list)

    def ajouter(self, article: Article) -> None:
        self.articles.append(article)

    def total(self) -> float:
        return sum(a.total() for a in self.articles)

    def appliquer_remise(self, pourcentage: float) -> float:
        if not 0 <= pourcentage <= 100:
            raise ValueError("le pourcentage doit être entre 0 et 100")
        return self.total() * (1 - pourcentage / 100)

    def article_le_plus_cher(self) -> Article | None:
        return max(self.articles, key=lambda a: a.total(), default=None)
