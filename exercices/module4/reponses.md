# Module 4 : réponses

Mesures sur un Apple M1 Pro (10 cœurs), Python 3.12.12, machine peu chargée.

## Benchmarks du cours

`bench_io.py`, 10 tâches qui attendent 0,1 s :

| Stratégie | Durée |
|---|---:|
| séquentiel | 1,03 s |
| 10 threads | 0,11 s |
| asyncio | 0,10 s |

`bench_cpu.py`, 4 calculs de 3 millions d'itérations :

| Stratégie | Durée |
|---|---:|
| séquentiel | 0,53 s |
| 4 threads | 0,51 s |
| 4 processus, pool déjà créé | 0,22 s |
| 4 processus, création du pool comprise | 0,25 s |

Les threads ne gagnent rien sur du calcul pur : le GIL les fait passer un
par un. J'ai ajouté la mesure "à froid" : le cours ne chronomètre qu'après
la création du pool, alors que l'utilisateur paie aussi le démarrage des
processus.

## Exercice 1 : le bon outil

1. Télécharger 200 pages : threads (ou asyncio), c'est de l'attente réseau.
2. Nombres premiers jusqu'à 10 millions sur les cœurs : processus.
3. Serveur à 10 000 connexions : asyncio, un thread par connexion coûterait
   trop de mémoire.
4. Redimensionner 50 images : processus (calcul par image), sauf si la
   bibliothèque d'images libère le GIL, auquel cas des threads suffisent.

## Exercice 2 : `analyser_tous` (`analyser.py`)

`ProcessPoolExecutor` avec `submit` et `as_completed`. `analyser` est au
niveau du module pour pouvoir être envoyée aux processus. Les erreurs de
lecture sont collectées par fichier, puis signalées ensemble. Le
`if __name__ == "__main__"` est obligatoire sur macOS (démarrage par
`spawn`, le module est réimporté par chaque processus).

## Exercice 3 : "tout passer en multiprocessing"

Si 95 % du temps est de l'attente de la base, les processus ne servent à
rien : il n'y a presque pas de calcul à répartir. Par la loi d'Amdahl, même
un calcul infiniment rapide ne gagnerait que 5 %. Il faut d'abord regarder
les requêtes (index, nombre d'allers-retours, requêtes groupées), puis
lancer les requêtes indépendantes en parallèle avec des threads ou
asyncio, dans la limite de connexions de la base.

## Exercice 4 : télécharger 500 fichiers puis les hacher

Deux étapes de nature différente. On mesure chacune séparément (temps
écoulé et temps CPU). Le téléchargement est de l'attente : on prend un pool
de threads borné. Pour le hachage, `hashlib` libère le GIL sur les gros
blocs : des threads peuvent suffire, à vérifier par une mesure avant de
payer le coût des processus. On peut enchaîner les deux dans le même
thread, sans tout télécharger d'abord, pour ne pas garder 500 fichiers en
mémoire.

## Exercice 5 : un million de futures

Un million d'objets `Future` en mémoire, une file interne énorme, et un
coût de soumission plus grand que le travail de chaque élément. Il vaut
mieux découper en lots (une tâche traite 1 000 éléments) et ne garder
qu'une fenêtre bornée de futures en cours : on soumet un nouveau lot quand
un ancien se termine.

## Exercice 6 : compteur partagé (`compteur.py`)

`valeur += 1` se fait en plusieurs étapes de bytecode : lire, ajouter,
écrire. Le GIL peut passer à un autre thread entre la lecture et
l'écriture, et une incrémentation est alors perdue. Avec un changement de
thread forcé entre les deux, j'obtiens 20 297 au lieu de 200 000. Il y a
deux solutions :

- un `Lock` autour de l'incrémentation ;
- mieux, pas d'état partagé : chaque thread renvoie son résultat (un
  `Counter`) et le thread principal additionne (`compter_par_resultats`).

## Exercice 7 : annulation après timeout

Non : la requête a pu arriver au serveur et être traitée, seule la réponse
est perdue. Côté client, il faut :

- envoyer une clé d'idempotence ou vérifier l'état avant de réessayer ;
- libérer la connexion dans un `finally` ;
- ne pas avaler `CancelledError`.

## Exercice 8 : `getsizeof` trompeur

`getsizeof` ne compte que le tableau de pointeurs de la liste, pas les
100 000 objets pointés (chacun a sa taille propre), ni l'allocateur. On
mesure avec `tracemalloc` (pic des allocations Python) ou la mémoire du
processus (RSS), sur le programme entier.

## Quiz

| # | Réponse |
|---|---|
| 1 | un seul thread exécute du code Python à la fois |
| 2 | des threads (ou asyncio) |
| 3 | des processus |
| 4 | non, le GIL les sérialise |
| 5 | un appel bloquant |
| 6 | 0,3 s |
| 7 | éviter que les enfants réexécutent le script |
| 8 | mesurer avant d'optimiser |
| 9 | un générateur |
| 10 | la vectorisation |

## Transfert vers le projet

Cas 4 : `src/mobilis/bornes.py`.

- Interroger l'API est de l'attente réseau : threads ou asyncio, au plus 8
  appels simultanés.
- Un décorateur `@reessayer` gère les codes 503, 504 et 429 (avec
  `Retry-After`).
- Les trois versions (séquentielle, threads, asyncio) sont mesurées contre
  le simulateur.
