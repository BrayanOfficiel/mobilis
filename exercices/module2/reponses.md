# Module 2 : réponses

## TP cache avec expiration (`cache_ttl.py`)

Décorateur à arguments, donc trois niveaux : `cache_ttl(duree_s)` renvoie
le décorateur, qui renvoie l'enveloppe. Le dictionnaire `cache` vit dans la
closure, un par fonction décorée.

- `time.monotonic()` et pas `time.time()` : l'heure système peut reculer
  (NTP, changement manuel), une durée calculée avec ne veut alors plus rien
  dire.
- L'horloge est un paramètre : les tests avancent le temps sans `sleep`.
- La clé est `(args, kwargs triés)`. Des arguments non hachables lèvent
  `TypeError`, voulu (voir exercice 7).
- `hits`, `miss` et `vider` sont des attributs de l'enveloppe.
- Lancer `python cache_ttl.py` : 3 appels, 2 calculs de 0,5 s, environ 1 s.

## Exercice 1 : `@trace` (`tracer.py`)

`functools.wraps` garde `__name__`, `__doc__` et `__wrapped__`. Typé avec
`ParamSpec` pour que mypy garde la signature de la fonction décorée.
(Fichier nommé `tracer.py` : `trace.py` masquerait le module `trace` de la
bibliothèque standard.)

## Exercice 2 : `@memoize` (`memoize.py`)

Mesuré sur ma machine : `fib(35)` en 1,04 s, `fib_memo(35)` en moins de
0,1 ms. Ça marche parce que l'appel récursif passe par le nom `fib_memo`,
qui désigne l'enveloppe : chaque sous-résultat n'est calculé qu'une fois
(O(n) au lieu de O(2^n)). Le cache ne se vide jamais : à réserver aux
fonctions pures à peu de valeurs différentes.

## Exercice 3 : `partial` et `reduce` (`fonctionnel.py`)

`arrondi2 = partial(round, ndigits=2)` et `reduce(math.gcd, nombres)`. Pour
une liste vide `reduce` lève une `TypeError` peu claire, je lève une
`ValueError` avant. (`math.gcd(*nombres)` fait la même chose depuis 3.9.)

## Exercice 4 : ordre des décorateurs

`@a @b def f` donne `f = a(b(f))` : `a` est l'enveloppe extérieure, exécutée
en premier à l'appel. Pour ne mesurer que le calcul autorisé :

```python
@verifier_droits
@chronometrer
def calcul(...): ...
```

Le contrôle d'accès passe d'abord ; s'il refuse, on ne chronomètre rien, et
quand il accepte, la mesure ne contient pas le temps du contrôle.

## Exercice 5 : retry sur une création de commande

Risque : le délai a expiré côté client mais le serveur a peut-être créé la
commande. Réessayer peut créer deux livraisons. L'opération n'est pas
idempotente.

Solutions : une clé d'idempotence générée une fois côté client et envoyée à
chaque essai (le serveur renvoie la commande existante) ; ou, avant de
réessayer, interroger le serveur pour savoir si la commande existe ; ne
réessayer automatiquement que les erreurs où l'on sait que rien n'a été fait
(429, 503 avant traitement).

## Exercice 6 : horodatage du TTL

Horodatage capturé avant un calcul de 2 s avec un TTL de 3 s : la valeur ne
reste utile que 1 s après la fin du calcul. Correction : prendre l'instant
après le calcul (c'est ce que fait `cache_ttl.py`), la valeur vit alors 3 s
pleines après sa production.

## Exercice 7 : arguments non hachables

Deux décisions défendables, sans sérialiser au hasard :

- refuser : laisser remonter le `TypeError`, documenter que la fonction
  doit recevoir des arguments hachables (comme `lru_cache`) ;
- contourner : ne pas mettre en cache cet appel (appeler la fonction
  directement et compter un "miss non cachable"), ou demander à l'appelant
  un `frozenset`/tuple ou une fonction `cle=` explicite.

## Exercice 8 : générateur consommé deux fois

Un générateur est épuisé après un parcours : le `len(list(gen))` du comptage
l'a vidé, le total parcourt un générateur vide.

- Source petite : matérialiser une fois dans une liste, puis compter et
  sommer.
- Source grosse : un seul passage qui calcule les deux en même temps
  (une boucle qui incrémente un compteur et un total), ou recréer le
  générateur depuis le fichier pour le second calcul.

## Quiz

| # | Réponse |
|---|---|
| 1 | `fn = decorateur(fn)` |
| 2 | préserver nom, docstring et signature |
| 3 | `nonlocal` |
| 4 | un niveau supplémentaire |
| 5 | mémorise les résultats |
| 6 | pures, aux arguments hachables |
| 7 | 5 |
| 8 | 10 |
| 9 | une compréhension de liste |
| 10 | ajouter un comportement transversal |

## Transfert vers le projet

Cas 2 : `src/mobilis/trajets.py` (pipeline de générateurs) et
`src/mobilis/decorateurs.py` (`@mesure` pour le temps et la mémoire,
`@tolerante` pour écarter et journaliser les lignes invalides).
