# Module 1 : réponses

## TP pipeline (`tp_pipeline.py`)

Chaque étage est un générateur, sauf l'agrégation finale qui consomme tout.
`lire_ventes` n'ouvre même pas le fichier avant le premier `next()` : on le
voit en lançant `python tp_pipeline.py`, les deux objets affichés sont des
`generator` et rien n'a été lu à ce moment-là.

Choix : `Decimal` pour les prix (pas de `float` pour de l'argent),
`defaultdict(Decimal)` pour additionner sans tester la présence de la clé.

## Exercice 1 : `Vecteur2D` (`vecteur.py`)

Méthodes spéciales nécessaires : `__add__` (v1 + v2), `__mul__` et
`__rmul__` (v * 3 et 3 * v), `__len__` (len), `__eq__` (==), `__repr__`.

En plus :

- `__hash__` : redéfinir `__eq__` met `__hash__` à `None`, l'objet ne
  pourrait plus aller dans un `set`. (Il reste mutable, donc à ne pas
  modifier une fois dans un ensemble.)
- `__abs__` pour la norme exacte, `__len__` ne peut renvoyer qu'un entier.
- `__bool__` : le vecteur nul est faux.
- renvoyer `NotImplemented` (et pas lever une erreur) quand l'autre opérande
  n'est pas du bon type, pour laisser Python essayer l'opération inverse.

## Exercice 2 : `fenetres` (`fenetres.py`)

Une `deque(maxlen=taille)` : l'ajout à droite fait sortir l'élément le plus
ancien tout seul. Mémoire constante (une seule fenêtre en mémoire), marche
sur un itérable infini. Si l'itérable est plus court que la taille, rien
n'est produit.

## Exercice 3 : choisir la structure

| Besoin | Structure |
|---|---|
| Mots les plus fréquents | `Counter(mots).most_common(n)` |
| Étudiants par promotion | `defaultdict(list)` |
| File FIFO | `deque` (`append` / `popleft` en O(1), alors que `list.pop(0)` est en O(n)) |
| Coordonnée immuable et légère | `NamedTuple` (ou dataclass `frozen=True, slots=True`) |

## Quiz

| # | Réponse |
|---|---|
| 1 | `__len__` |
| 2 | rendre les instances immuables (et hachables) |
| 3 | paresseux, mémoire constante |
| 4 | le second parcours est vide (générateur épuisé) |
| 5 | `Counter` |
| 6 | `deque` |
| 7 | un objet générateur |
| 8 | documentent le code, vérifiées par mypy, sans effet à l'exécution |
| 9 | la liste par défaut est partagée entre les appels |
| 10 | un namedtuple (ou une dataclass frozen) |

## Transfert vers le projet

Cas 1 : `src/mobilis/stations.py`, dataclass `Station` gelée et validée,
`Statut` en Enum. Détail des décisions dans `docs/journal_anomalies.md`.

Défi avancé : cas limite des codes en double, couvert par
`test_doublon_garde_la_mise_en_service_la_plus_recente`.
