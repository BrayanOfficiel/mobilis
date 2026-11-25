---
title: "Mobilis : une bibliothèque Python sur données réelles"
subtitle: "Dossier technique, PYA-701 Python avancé"
---

# Mobilis : une bibliothèque Python sur données réelles

Dossier technique, cours PYA-701 (Python avancé), M1.

Équipe : [Prénom NOM 1] et [Prénom NOM 2].

Dépôt : [lien du dépôt Git].

Version du code décrite : commit `[hash]`, novembre 2026.

## Sommaire

1. Présentation
2. Conception
3. Techniques avancées
4. Qualité
5. Résultats
6. Bilan

# 1. Présentation

## 1.1 Le besoin

Mobilis exploite un réseau de vélos en libre-service d'environ 150 stations.
Chaque analyste avait jusqu'ici ses propres scripts, et les chiffres ne
concordaient jamais. La direction veut, pour son comité trimestriel :

- la fréquentation des stations (lesquelles se vident le matin, profil
  horaire) ;
- le chiffre d'affaires par mois et par formule, et l'effet de la hausse
  tarifaire du 1er octobre 2026 ;
- l'état du réseau en temps réel, et savoir si le système des bornes est
  d'accord avec le référentiel des stations.

Notre travail est la bibliothèque commune `mobilis`, utilisée par des
développeurs et des analystes qui ne connaissent pas les pièges des
données. Elle doit donner des chiffres justes, reproductibles et expliqués.

## 1.2 Le périmètre

Les données sont les exports bruts du kit : `stations.csv`,
`trajets_2026-08_2026-10.csv.gz` (155 631 lignes), `abonnes.jsonl`,
`tarifs.json`, la spécification de facturation (règles R1 à R12, exemples
E1 à E6) et le simulateur de l'API des bornes.

Les cinq cas du sujet sont traités :

| Cas | Question | Module du code | Commande |
|---|---|---|---|
| 1 | Combien de stations sont exploitables ? | `stations.py` | `mobilis stations` |
| 2 | Quelles stations se vident le matin ? | `trajets.py` | `mobilis frequentation` |
| 3 | Combien chaque mois a-t-il rapporté ? | `abonnes.py`, `facturation.py` | `mobilis facturation` |
| 4 | Quel est l'état du réseau maintenant ? | `bornes.py` | `mobilis etat` |
| 5 | L'équipe peut-elle tout refaire seule ? | `cli.py`, `tests/`, CI | `pip install -e ".[dev]"` |

Hors périmètre : interface graphique, base de données, graphiques. Le cœur
est écrit en Python standard, comme demandé. Les seules dépendances sont
des outils de développement (pytest, pytest-cov, mypy, ruff).

Une règle a guidé tout le projet : aucun fichier du kit n'est corrigé à la
main. Le code détecte, compte et traite chaque anomalie, et le journal des
anomalies (`docs/journal_anomalies.md`, repris en partie 5) justifie chaque
décision.

## 1.3 L'équipe

| Membre | Cas pris en charge | Autres rôles |
|---|---|---|
| [Prénom NOM 1] | [à compléter] | [à compléter] |
| [Prénom NOM 2] | [à compléter] | [à compléter] |

# 2. Conception

## 2.1 Architecture

Le paquet suit la disposition `src/` : les tests importent la version
installée, comme un utilisateur. Chaque module correspond à une source de
données ou à une question, et la commande `mobilis` ne fait qu'assembler et
afficher.

```
                       cli.py  (commande mobilis : lit les options, affiche)
                          |
   +-------------+--------+---------+--------------+
   |             |                  |              |
stations.py  trajets.py       facturation.py    bornes.py
 (cas 1)      (cas 2)            (cas 3)          (cas 4)
   |             |  \               |  \              |
   |             |   +-- trajets_propres  abonnes.py  |
   |             |       (chaîne commune)  (cas 3)    |
   |             |                                    |
   +------+------+------------------+-----------------+
          |                         |
     journal.py               decorateurs.py
  (Journal, LigneRejetee)   (@mesure, @tolerante)
```

Les dépendances vont toujours vers le bas. `facturation.py` réutilise la
chaîne de nettoyage des trajets du cas 2 (`trajets_propres`) au lieu de la
réécrire : les doublons (R11), les fins avant début (R10) et les stations
inconnues (R12) sont traités une seule fois, au même endroit, et les deux
cas comptent exactement les mêmes 154 868 trajets. `bornes.py` ne dépend
que de `stations.py`, pour la comparaison avec le référentiel.

`journal.py` et `decorateurs.py` sont transverses. Le `Journal` compte les
anomalies par type et garde quelques exemples, avec une mémoire bornée quel
que soit le volume.

## 2.2 Modèle de données

Toutes les entités sont des `dataclass(frozen=True, slots=True)` validées
dans `__post_init__`. Un objet invalide ne peut pas exister : il n'y a pas
de contrôle à refaire plus loin.

| Classe | Module | Invariants vérifiés |
|---|---|---|
| `Station` | `stations.py` | code `MB-dddd`, capacité positive, coordonnées présentes |
| `Trajet` | `trajets.py` | instants avec fuseau ; station et heure d'arrivée vont ensemble |
| `Abonnement` | `abonnes.py` | fin postérieure au début, pas de formule "occasionnel" |
| `Bareme`, `Grille`, `Tarifs` | `facturation.py` | montants en `Decimal` |
| `EtatStation` | `bornes.py` | nombres entiers, horodatage |

Les valeurs à liste fermée sont des `Enum` : `Statut` (7 graphies dans le
fichier ramenées à 3 valeurs), `TypeVelo`, `TypeJour`, `Formule`, et un
`Enum` par famille d'anomalies (`TypeAnomalie`, `AnomalieTrajet`,
`AnomalieAbonne`, `AnomalieFacturation`). Le journal est indexé par ces
`Enum`, et la commande associe à chacune sa décision (corrigée, écartée,
gardée, signalée).

Les valeurs dérivées sont des propriétés calculées, jamais stockées :
`Station.exploitable`, `Trajet.duree`, `EtatStation.velos`, `vide`,
`pleine`. Elles ne peuvent pas se désynchroniser.

Les dates de trajet sont toujours des instants avec fuseau. Le jour, l'heure
et le mois d'un trajet sont calculés en heure de Paris (`zoneinfo`) au moment
où on en a besoin. C'est ce qui règle l'exemple E6 : un trajet qui part à
02:40 heure d'été et arrive à 02:10 heure d'hiver dure bien 30 minutes.

## 2.3 Interfaces

**Une classe abstraite pour la tarification.** La spécification décrit un
calcul commun à toutes les formules (R4, R5) et une règle qui ne s'applique
qu'aux abonnements, le plafond journalier (R6). Nous avons choisi une ABC,
parce que la hiérarchie est entièrement à nous et que les deux classes
partagent du code :

```python
class Tarification(ABC):
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
```

`TarifOccasionnel.facturer` arrondit simplement le prix. `TarifAbonnement`
garde ce que chaque abonné a déjà payé dans la journée (état propre à
l'instance) et ne facture que ce qui reste sous le plafond. La différence
entre les deux n'est pas un paramètre : l'une a un état, l'autre non. Un
abonnement sans plafond est refusé à la construction.

La classe `Facturation` compose le tout. Elle crée une `Tarification` par
grille et par formule, choisit la formule active (R2, R3) et la grille en
vigueur (R1), puis traite les cas particuliers (R8 fantôme, R9
non-restitution) avant de déléguer à la tarification.

**Des Protocol pour la source des bornes.** La photo du réseau n'a besoin
que de deux opérations : `pages()` (les codes, page par page) et
`etat(code)`. Le `Protocol` `SourceBornes` les décrit sans imposer
d'héritage. Le vrai client et le faux client des tests le respectent tous
les deux, et mypy le vérifie. Ici une ABC n'apporterait rien, car aucun code
n'est partagé.

## 2.4 Choix techniques

| Choix | Raison |
|---|---|
| `Decimal` pour tous les montants, `json.load(parse_float=Decimal)` | R7 interdit le float ; un tarif écrit sans guillemets ne passe jamais par un float |
| Arrondi `ROUND_HALF_UP` au centime | R7 : "la moitié vers le haut" (Python arrondit par défaut au pair) |
| `zoneinfo("Europe/Paris")` | jours locaux, changement d'heure du 25 octobre |
| `csv`, `gzip`, `json` de la bibliothèque standard | le sujet demande un cœur sans dépendance ; lecture en flux |
| `urllib` + `ThreadPoolExecutor` pour l'API | client standard, choix mesuré (partie 3.4) |
| clé de l'API par `--cle` ou `MOBILIS_API_CLE` | aucun secret dans le dépôt |
| chemin des données par `--donnees` ou `MOBILIS_DONNEES` | le kit n'est pas versionné |

# 3. Techniques avancées

Chaque technique répond à un besoin du cas où elle apparaît. Cette partie
dit où elle est, et pourquoi.

## 3.1 Générateurs

**La chaîne des trajets (cas 2 et 3).** Le fichier des trajets doit pouvoir
être cent fois plus gros sans être chargé en mémoire. Chaque étape est un
générateur qui prend un itérable et en produit un autre :

```
lire_lignes -> convertir_trajets -> dedoublonner -> coherents
            -> signaler_inconnues -> du_mois -> Frequentation / Facturation
```

Un seul trajet est en mémoire à la fois. Le dédoublonnage est le seul
endroit qui garde un état. Comme les doublons suivent toujours l'original
de près dans l'export, il ne retient que les 1 000 derniers identifiants
(`deque` et `set`) :

```python
def dedoublonner(trajets, journal, fenetre=1000):
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
```

Mesure : pic de 2,6 Mio sur le fichier réel (`mobilis --mesure
frequentation`). Le test `test_memoire_constante` montre qu'un fichier 5
fois plus gros ne fait pas monter le pic de plus de 10 %. Piège rencontré :
sous 20 000 lignes, les compteurs restent sous 256, des petits entiers que
Python partage, et le pic de référence est faussé. Le test utilise donc
20 000 contre 100 000 lignes.

**La pagination de l'API (cas 4).** `ClientBornes.pages()` produit les codes
page par page. La photo envoie les requêtes des stations d'une page dès
qu'elle est lue, pendant que la page suivante est demandée. Ce gain est
d'environ 2 s sur une photo d'une dizaine de secondes.

## 3.2 Décorateurs

**`@tolerante`** (`decorateurs.py`) transforme un convertisseur de ligne en
étape de pipeline qui ne s'arrête jamais. Si le convertisseur lève
`LigneRejetee`, la ligne est écartée et notée dans le journal avec son
numéro. Toute autre exception remonte, car c'est un bug et non une donnée
sale. Il est utilisé deux fois, pour des formats différents :
`convertir_trajets` (CSV) et `convertir_abonnements` (JSON Lines).

**`@mesure(libelle)`** journalise la durée d'un appel et, si `tracemalloc`
tourne (option `--mesure`), son pic mémoire. Il décore `analyser_trajets`
et `facturer_fichier`. Il mesure dans un `finally`, donc même si la
fonction échoue. Une remarque est notée dans la docstring : sur une fonction
génératrice, il ne mesurerait que la création du générateur.

**`@reessayer` et `@reessayer_async`** (`bornes.py`) refont un appel à
l'API en cas de 429, 503, 504 ou d'erreur réseau, au plus 4 fois. Ils
respectent `Retry-After` quand le serveur l'envoie, sinon ils attendent
0,2 s puis doublent à chaque essai. Les erreurs définitives (400, 401, 404)
remontent tout de suite. Il en faut deux versions : dans une coroutine,
l'attente doit être un `await asyncio.sleep`, sinon toute la boucle se
fige. Les deux partagent la règle de calcul de l'attente (`delai_avant`).

Tous sont typés avec `ParamSpec` : mypy garde la signature exacte de la
fonction décorée, et `functools.wraps` garde son nom et sa docstring.

## 3.3 POO avancée

- `dataclass(frozen=True, slots=True)` et validation dans `__post_init__`
  pour toutes les entités (partie 2.2).
- Propriétés calculées pour les valeurs dérivées.
- ABC `Tarification` et deux implémentations (partie 2.3).
- `Protocol` pour la source des bornes, et dans les exercices du module 3.
- Composition : `Facturation` possède un dictionnaire de `Tarification`,
  `Abonnes` regroupe les `Abonnement` par identifiant.
- `__contains__` et `__len__` sur `Abonnes` et `Journal`, pour écrire
  `abonne_id in abonnes`.

Mesure de `slots=True` (exercice du module 3, un million d'objets à trois
champs) : 92,0 Mio sans slots contre 61,5 Mio avec. Dans le projet, le gain
réel est faible : les trajets passent un par un dans la chaîne. L'intérêt
de `slots` est surtout d'interdire un attribut ajouté par erreur.

## 3.4 Concurrence

Photographier les 149 stations de l'API demande au moins 155 requêtes
(6 pages et 149 états). L'API met en moyenne un quart de seconde à
répondre, et parfois 2 à 3 s. Elle refuse au-delà de 8 requêtes
simultanées. C'est de l'attente réseau, pas du calcul : le GIL est relâché
pendant l'attente, donc threads ou asyncio, pas de processus.

Trois versions sont gardées dans `bornes.py` pour la comparaison :

- séquentielle ;
- `ThreadPoolExecutor` à 8 threads ;
- asyncio avec un `TaskGroup`.

Dans les deux clients, un sémaphore de 8 borne les requêtes en vol, pages
comprises. Le sémaphore est pris autour de la requête seulement, pas
pendant l'attente entre deux essais.

Mesures (`mobilis etat --comparer`, trois passages, Apple M1 Pro,
Python 3.12) :

| Stratégie | Passage 1 | Passage 2 | Passage 3 |
|---|---:|---:|---:|
| séquentielle | 63,7 s | 77,9 s | 69,2 s |
| threads (8) | 12,4 s | 10,4 s | 9,4 s |
| asyncio (8 en vol) | 9,4 s | 10,8 s | 12,8 s |

Sur 2 182 réponses du serveur pendant ces mesures, 79 étaient des 503 et
aucune un 429 : le sémaphore suffit à respecter la limite.

**Choix : les threads.** Threads et asyncio vont aussi vite, et l'écart
change de sens d'un passage à l'autre : c'est la limite de 8 requêtes du
serveur qui fixe le débit, pas le client. Les threads utilisent `urllib`.
La bibliothèque standard n'a pas de client HTTP asynchrone, et la version
asyncio repose sur un petit client écrit à la main sur `open_connection`
(HTTP/1.0). C'est plus de code à maintenir pour aucun gain mesuré. asyncio
deviendrait le bon choix pour des milliers de requêtes simultanées, ce que
l'API interdit.

Le séquentiel dépasse largement les 15 s demandées ; les deux versions
concurrentes tiennent avec une marge de 2 à 5 s.

Une borne en panne (504 permanent) ne doit pas faire échouer la photo des
autres. Chaque station est demandée par `etat_ou_erreur`, qui renvoie
l'état ou l'erreur. La photo range les stations dans `etats` ou
`injoignables`.

# 4. Qualité

## 4.1 Stratégie de tests

90 tests dans `tests/`, tous au vert en 6 s, plus 39 tests pour les
exercices du cours.

| Fichier | Tests | Ce qui est vérifié |
|---|---:|---|
| `test_stations.py` | 26 | statuts paramétrés, validation, corrections, lignes écartées, doublons, kit réel |
| `test_trajets.py` | 16 | 3 formats de date, changement d'heure, doublons, mémoire constante, bout en bout |
| `test_facturation.py` | 18 | E1 à E6 paramétrés, tranche d'une seconde, arrondi, grille à la date locale, plafond, pénalité |
| `test_bornes.py` | 15 | réessai (mock), Retry-After, client urllib et asyncio simulés, photo avec borne en panne |
| `test_cli.py` | 8 | chaque sous-commande sur un mini kit, erreurs d'usage, API éteinte |
| `test_abonnes.py` | 3 | lignes coupées récupérées ou écartées, bornes des périodes |
| `test_decorateurs.py` | 3 | `@mesure` (caplog, tracemalloc, exception), `@tolerante` |
| `test_demarrage.py` | 1 | le paquet s'importe |

Principes suivis :

- **Les tests ne dépendent ni du kit ni du serveur.** `tests/conftest.py`
  fabrique un petit kit dans un dossier temporaire, aux mêmes formats que le
  vrai : `stations.csv` en cp1252 avec CRLF et une capacité `NC`, trajets en
  gzip avec un doublon et une fin avant début, une ligne d'abonné coupée.
  Les 4 tests qui lisent le vrai kit sont ignorés (`skipif`) quand il est
  absent, comme dans la CI.
- **Paramétrage.** Les six exemples de la spécification sont un seul test
  paramétré, avec un identifiant par cas (`E1` à `E6`) ; c'est le contrat
  avec la direction commerciale.
- **Mocks aux frontières seulement.** `unittest.mock.patch` remplace
  `urllib.request.urlopen` et `asyncio.open_connection`. Le reste du client
  (pagination, décodage, réessai) s'exécute pour de vrai. Les décorateurs
  de réessai acceptent une fonction `dormir` : les tests vérifient les
  attentes (0,2 s puis 0,4 s, ou 1 s sur `Retry-After`) sans attendre.
- **Cas limites.** Tranche entamée d'une seconde, arrondi d'un demi-centime,
  trajet à 23h30 UTC le 30 septembre (déjà en octobre à Paris), plafond sur
  deux jours, abonnement qui finit la veille, pénalité hors plafond, API
  entièrement éteinte.

Couverture (`pytest --cov`, lignes et branches) : 95 %. Les lignes non
couvertes sont surtout de l'affichage (`cli.py`, 89 %) et les erreurs réseau
réelles du client (`bornes.py`, 93 %). Nous n'avons pas cherché les 100 % :
la logique de facturation, les décorateurs et le journal sont à 100 %.

## 4.2 Typage, style, CI

- `mypy --strict` sur `src` et `tests`, sans erreur. Aucun `# type: ignore`
  dans `src`. Les deux de `tests` sont voulus : un test vérifie qu'on ne
  peut pas modifier une `Station` figée, l'autre construit des stations
  invalides exprès. Chacun porte son code d'erreur précis.
- `ruff check` (règles E, F, W, I, B, UP, SIM) et `ruff format`.
- CI GitHub Actions (`.github/workflows/qualite.yml`) : ruff, mypy, pytest
  avec couverture et tests des exercices, sous Python 3.11, 3.12 et 3.13
  (la bibliothèque annonce `requires-python >= 3.11`).
- `pre-commit` avec des hooks locaux : formatage, lint et mypy avant chaque
  commit, avec les versions du venv du projet.
- Installation testée depuis un clone vierge : `pip install -e ".[dev]"`,
  puis `pytest` (86 réussis, 4 ignorés sans le kit, 90 avec).

## 4.3 Gestion des erreurs

Les erreurs sont traitées à trois niveaux :

- **Une donnée sale** lève `LigneRejetee` : la ligne est écartée et comptée,
  le traitement continue.
- **Une erreur d'utilisation** (fichier absent, clé d'API manquante) donne un
  message clair et le code de sortie 2, sans trace Python.
- **Un bug** (toute autre exception) remonte : un convertisseur ne doit pas
  le cacher.

# 5. Résultats

Tous les chiffres se reproduisent avec la commande indiquée, à partir des
fichiers bruts du kit (`export MOBILIS_DONNEES=chemin/vers/donnees`).

## 5.1 Cas 1 : le référentiel des stations

`mobilis stations`

153 lignes lues pour 150 codes. **147 stations retenues, dont 141
exploitables** (en service), 3 hors service (MB-0019, MB-0113, MB-0143) et
3 fermées (MB-0013, MB-0047, MB-0105). 6 lignes écartées.

## 5.2 Cas 2 : les trajets

`mobilis frequentation`

**154 868 trajets retenus** sur 155 631 lignes, sur 92 jours (65 de
semaine, 27 de week-end).

En semaine, le profil a deux pointes : 211 départs par jour à 8 h et 202 à
17 h, sur tout le réseau. Le week-end, la courbe monte doucement jusqu'à un
maximum de 131 départs à 15 h.

Stations qui se vident le matin (7 h à 10 h) et se remplissent le soir
(17 h à 20 h), en semaine, solde moyen de vélos par jour :

| Station | Nom | Matin | Soir |
|---|---|---:|---:|
| MB-0142 | Lycée Jeanne-d'Arc | -26,8 | +21,3 |
| MB-0023 | Place des Cèdres | -10,9 | +9,0 |
| MB-0133 | Square des Cèdres | -9,3 | +8,2 |
| MB-0057 | Square de la Poste | -8,0 | +7,9 |
| MB-0144 | Place Jeanne-d'Arc | -6,8 | +6,4 |

MB-0142 perd près de 27 vélos chaque matin de semaine : c'est la première
station à rééquilibrer.

Performance : 1,2 s pour tout le fichier sans mesure mémoire, pic de
2,6 Mio avec `tracemalloc` (qui ralentit l'exécution à environ 5 s).

## 5.3 Cas 3 : la facturation

`mobilis facturation`

Chiffre d'affaires en euros, par mois local de début du trajet :

| Mois | Annuel | Mensuel | Solidaire | Occasionnel | Total | dont pénalités |
|---|---:|---:|---:|---:|---:|---:|
| 2026-08 | 15 210,50 | 5 321,50 | 539,25 | 41 882,80 | 62 954,05 | 5 100,00 |
| 2026-09 | 20 711,00 | 7 903,00 | 1 007,75 | 62 698,20 | 92 319,95 | 6 600,00 |
| 2026-10 | 21 032,20 | 8 058,60 | 1 032,75 | 63 756,25 | 93 879,80 | 5 400,00 |
| Total | 56 953,70 | 21 283,10 | 2 579,75 | 168 337,25 | **249 153,80** | 17 100,00 |

Les usagers occasionnels apportent 68 % du chiffre d'affaires avec 31 % des
trajets (47 546 sur 154 868).

**Effet de la nouvelle grille.** Nous avons refacturé les mêmes trajets
d'octobre avec l'ancienne grille (`Tarifs.avant(date)`). À comportement
égal, hors pénalités (inchangées) :

| Octobre 2026 | Montant |
|---|---:|
| avec la nouvelle grille | 88 479,80 € |
| avec l'ancienne grille | 72 404,95 € |
| écart | +16 074,85 € (+22,2 %) |

74 % de l'écart vient des occasionnels (+11 914,05 €) ; la formule
solidaire n'a pas changé de prix. Le nombre de trajets baisse entre
septembre (61 718) et octobre (51 641), mais nous ne pouvons pas dire quelle
part vient de la hausse et quelle part de la saison : il faudrait au moins
l'octobre de l'année précédente.

Conformité : les exemples E1 à E6 passent (test paramétré).

## 5.4 Cas 4 : l'état en temps réel

`mobilis etat` (simulateur lancé, clé dans `MOBILIS_API_CLE`)

L'API liste 149 stations, 146 répondent. MB-0079, MB-0100 et MB-0150 sont
toujours injoignables (504). Les stations vides ou pleines changent à chaque
photo. Le désaccord avec le référentiel, lui, est stable :

- MB-0013, MB-0047 et MB-0105, retenues dans le référentiel, sont absentes
  de l'API. Ce sont exactement les trois stations fermées, les deux sources
  se recoupent.
- MB-0151 et MB-0152 sont dans l'API mais pas dans `stations.csv`, sans
  doute des stations récentes.
- MB-0028, MB-0090 et MB-0109, écartées du référentiel (capacité ou
  coordonnées absentes), répondent dans l'API. L'API pourrait compléter
  leur capacité.
- MB-0019, MB-0113 et MB-0143, hors service dans le référentiel, répondent.
  Leur statut est peut-être en retard.
- Pour 137 stations sur 146, la capacité de l'API (vélos et places libres)
  diffère de celle du référentiel. Nous ne savons pas laquelle est juste :
  nous le signalons sans corriger, et "vide" et "pleine" sont jugées sur
  l'API, qui donne l'état réel.

Durée de la photo : 9 à 12 s avec les threads (partie 3.4).

## 5.5 Journal des anomalies

Le journal complet, avec les exemples, est dans `docs/journal_anomalies.md`.
Synthèse :

**stations.csv** (cp1252, CRLF, `;`, décimales à virgule)

| Anomalie | Lignes | Décision | Justification |
|---|---:|---|---|
| Statut écrit de 7 façons | 153 | normalisé | 3 états sans ambiguïté |
| Espaces en trop | 37 | corrigé | bruit de saisie |
| Date AAAA-MM-JJ au lieu de JJ/MM/AAAA | 6 | corrigé | format non ambigu |
| Latitude et longitude inversées (MB-0064, MB-0135) | 2 | corrigé | l'échange ramène le point dans l'agglomération |
| Capacité `NC` (MB-0028, MB-0090) | 2 | écarté | inventer une capacité fausserait le cas 4 |
| Coordonnées absentes (MB-0109) | 1 | écarté | station impossible à placer |
| Code en double (MB-0033, MB-0068, MB-0104) | 3 | écarté (le plus ancien) | remise en service après travaux |

**Trajets** (gzip, UTF-8, non trié)

| Anomalie | Nombre | Décision | Justification |
|---|---:|---|---|
| Date en UTC (`Z`) | 22 772 dates | converti | instant non ambigu |
| Date `JJ/MM/AAAA` sans fuseau | 10 293 dates | heure de Paris | les trajets voisins le montrent |
| Trajet transmis deux fois | 620 | écarté (R11) | lignes identiques et consécutives |
| Fin avant le début | 143 | écarté (R10) | impossible de savoir quelle date est fausse |
| Station inconnue (MB-0998, MB-0999) | 111 | gardé, signalé (R12) | le trajet a eu lieu |
| Sans arrivée | 78 | gardé | le départ est réel ; pénalité R9 |
| Distance absente | 4 705 | gardé | ne sert à aucun calcul |

**abonnes.jsonl**

| Anomalie | Lignes | Décision | Justification |
|---|---:|---|---|
| Formule avec majuscules ou espaces | 147 | corrigé | 3 formules sans ambiguïté |
| Ligne vide | 3 | écartée | rien à lire |
| Ligne coupée, champs utiles entiers | 2 | corrigé | seule la commune est perdue |
| Ligne coupée avant la fin des champs utiles | 4 | écartée | formule ou dates perdues |

**Facturation**

| Situation | Trajets | Décision |
|---|---:|---|
| Abonné absent du fichier (118 identifiants) | 197 | occasionnel, signalé au service client (R3) |
| Abonnement expiré ou pas commencé | 701 | occasionnel (R3) |
| Trajet fantôme | 1 944 | non facturé, signalé à la maintenance (R8) |
| Non restitué (pas d'arrivée ou plus de 24 h) | 114 | pénalité de 150 € (R9) |

Décisions prises là où la spécification ne dit rien, chacune couverte par
un test :

- un trajet à cheval sur deux jours compte pour le jour (et le mois) local
  de son début ;
- le plafond R6 est réparti dans l'ordre du fichier : le total du jour n'en
  dépend pas ;
- une ligne d'abonné coupée n'est récupérée que si l'identifiant, la
  formule et les deux dates sont entiers ;
- la pénalité R9 est rangée sous la formule de l'usager.

# 6. Bilan

## 6.1 Difficultés

- **Les fuseaux horaires.** Trois formats de date, dont un sans fuseau, et
  un changement d'heure dans la période. Nous avons converti dès la lecture
  en instants avec fuseau, et calculé les jours locaux seulement à
  l'affichage ou à la facturation.
- **Mesurer la mémoire pour de vrai.** Le premier test de mémoire constante
  échouait au hasard. La cause était le cache des petits entiers de Python,
  qui faussait le pic de référence sur les petits fichiers.
- **Le plafond journalier sur un fichier non trié.** On ne peut jamais
  "fermer" une journée. Il faut garder le cumul de chaque abonné et de
  chaque jour jusqu'à la fin.
- **Tester du code réseau sans réseau.** Il a fallu rendre l'attente
  injectable dans les décorateurs, et simuler `open_connection` avec un
  vrai `StreamReader`.

## 6.2 Limites

- Le dédoublonnage ne voit pas un doublon séparé de plus de 1 000 lignes de
  l'original. C'est le prix d'une mémoire bornée ; dans le kit, ils sont
  tous consécutifs.
- Le cumul du plafond (cas 3) grandit avec le nombre d'abonnés et de jours :
  23 à 30 Mio de pic pour la facturation (`mobilis --mesure facturation`),
  contre 2,6 Mio pour la fréquentation. Pour un fichier cent fois plus long, il faudrait un fichier
  trié par jour, ou vider les jours terminés.
- Les jours fériés (15 août) comptent comme des jours ordinaires dans le
  profil horaire.
- L'effet de la hausse est calculé à comportement égal. Nous ne mesurons
  pas l'effet de la hausse sur la demande.
- La CI est écrite mais n'a tourné que localement, faute de dépôt distant
  au moment de la rédaction [à mettre à jour].

## 6.3 Améliorations possibles

- Multiprocessing sur la fréquentation (calcul CPU), à mesurer contre le
  coût de transfert des compteurs entre processus.
- Un export CSV des résultats pour les analystes, en plus de l'affichage.
- Signaler à part les stations dont le statut diffère entre l'API et le
  référentiel, et proposer une mise à jour du référentiel.

## 6.4 Bilan individuel

### [Prénom NOM 1]

[Une demi-page à écrire soi-même : ce que j'ai fait (cas, fichiers,
commits), la difficulté technique principale et comment je l'ai résolue, ce
que j'ai appris par rapport au cours, ce que je ferais autrement.]

### [Prénom NOM 2]

[Une demi-page à écrire soi-même, mêmes points.]
