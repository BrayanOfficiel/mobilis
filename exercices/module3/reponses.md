# Module 3 : réponses

## TP chrono (`chrono.py`)

Deux versions équivalentes :

- la classe `Chrono` (`__enter__` / `__exit__`) ;
- la fonction `chrono` décorée par `@contextmanager`.

Dans les deux cas, la durée est prise à la sortie même si le bloc lève une
exception : grâce au `finally` pour le générateur, parce que `__exit__` est
toujours appelé pour la classe.

`__exit__` renvoie `False` : l'exception remonte, le chrono ne doit pas la
cacher. mypy demande alors `Literal[False]` comme type de retour (avec
`bool`, il suppose que le gestionnaire peut avaler les exceptions).

L'horloge est un paramètre, comme dans le TP du module 2 : les tests
donnent des instants fixes au lieu de dormir.

## Exercice 1 : `Compte` (`compte.py`)

Le setter refuse un solde négatif, `__init__` passe par lui, donc
l'invariant tient aussi après la construction. Un solde qui n'est pas un
`Decimal` fini (NaN, infini, float) est refusé.

`decouvert` vaut toujours `False` puisque le solde ne peut pas être
négatif. Ce que ça révèle : cette propriété est du code mort, elle découle
directement de l'invariant. Soit on autorise un découvert (avec une limite,
et la propriété a un sens), soit on ne l'écrit pas. Il ne faut pas exposer
une donnée dérivée qui ne peut prendre qu'une valeur.

## Exercice 2 : Protocol `Transformateur` (`transformateurs.py`)

`Majuscules` et `Inverser` n'héritent de rien : mypy vérifie qu'ils ont une
méthode `transformer(str) -> str` au moment où on les passe à
`appliquer_tous`.

## Exercice 3 : ABC ou Protocol ?

1. Hiérarchie de formes que l'on maîtrise : ABC (héritage explicite, on peut
   partager des méthodes concrètes).
2. Tout objet qui a `read()` : Protocol, on ne peut pas faire hériter un
   fichier ou un flux réseau de notre classe.
3. Empêcher l'instanciation tant qu'une méthode manque : ABC, c'est elle qui
   lève `TypeError` à l'instanciation ; un Protocol n'est vérifié que par
   mypy.

## Exercice A : invariant d'un intervalle (`intervalle.py`)

- `Intervalle` : dataclass figée. Une fois construite, on ne peut plus
  changer ses bornes, donc la validation de `__post_init__` suffit.
- `IntervalleModifiable` : bornes en lecture seule (properties sans setter)
  et une seule méthode `deplacer(debut, fin)` qui valide les deux ensemble.
  Deux setters séparés obligeraient à passer par un état invalide pour
  déplacer l'intervalle vers la droite, par exemple de (0, 5) à (6, 10).

## Exercice B : `__exit__` qui renvoie toujours `True`

L'erreur de parsing est avalée : le `with` se termine comme si tout allait
bien, et le code suivant travaille sur des données incomplètes sans le
savoir. Correction : fermer, puis renvoyer `False` (ou `None`). Si on veut
traiter une erreur précise, on teste `exc_type` et on ne renvoie `True` que
pour elle.

## Exercice C : Protocol au runtime

Faux. L'annotation n'est lue que par mypy. À l'exécution, Python accepte
n'importe quel objet, et l'erreur arrive (`AttributeError`) seulement au
moment de l'appel de `exporter()`. `@runtime_checkable` permet un
`isinstance`, mais il ne vérifie que la présence des noms, pas les
signatures. Pour une entrée utilisateur, il faut une vraie validation.

## Exercice D : slots dans une hiérarchie

La sous-classe sans `__slots__` recrée un `__dict__` pour chaque instance.
On paie alors les slots de la base et le dictionnaire, et le gain disparaît.
Chaque classe de la hiérarchie doit déclarer ses propres `__slots__`, même
vides.

## Exercice E : `ExitStack` et ouverture partielle

On ouvre les fichiers dans un `with ExitStack() as pile`, avec
`pile.enter_context(open(...))` pour chacun. Si le quatrième lève une
exception, la pile ferme les trois premiers en sortant du `with`.
`compter_tous` dans `lecteurs.py` fait exactement ça, et
`test_exitstack_ferme_les_premiers` le vérifie.

## Atelier : registre de lecteurs (`lecteurs.py`)

- Le contrat `LecteurEnregistrements` ne demande que
  `enregistrements() -> Iterator[dict[str, str]]`, c'est le seul besoin de
  l'appelant.
- `LecteurCSV` possède un fichier, c'est donc lui le gestionnaire de
  contexte. `LecteurMemoire` n'a rien à fermer et ne l'est pas.
- Le champ manquant lève `ChampManquant` avec la source et le numéro de
  ligne, sans recopier la ligne.
- J'ai choisi un Protocol plutôt qu'une ABC : les deux lecteurs ne
  partagent aucun code, et un faux lecteur de test n'a pas besoin d'hériter
  de quoi que ce soit. Une ABC aurait du sens si plusieurs lecteurs
  partageaient la validation ; ici, c'est une simple fonction `verifier`.

## Atelier, livrable 5 : mesure de `__slots__` (`mesure_slots.py`)

Mesure faite avec Python 3.12.12 sur macOS : 1 000 000 de `Releve` à trois
champs, meilleur de 3 essais, mémoire tracée par tracemalloc (objets
seulement, pas tout le processus).

| Classe | Temps de création | Mémoire |
|---|---:|---:|
| `@dataclass` | 1,00 s | 92,0 Mio |
| `@dataclass(slots=True)` | 0,79 s | 61,5 Mio |

Environ un tiers de mémoire en moins. Cela ne compte que pour des millions
d'objets. Dans le projet, `Trajet` est en `slots=True` mais les trajets
passent un par un dans le pipeline : le gain réel y est faible, et c'est
surtout l'interdiction d'ajouter un attribut par erreur qui sert.

## Quiz

| # | Réponse |
|---|---|
| 1 | exposer un attribut tout en contrôlant lecture/écriture ou en le calculant |
| 2 | réduire la mémoire en supprimant le `__dict__` |
| 3 | `__enter__` / `__exit__` |
| 4 | l'endroit où s'exécute le corps du bloc `with` |
| 5 | ne peut pas être instanciée (`TypeError`) |
| 6 | structurellement, via mypy |
| 7 | pour ne pas masquer l'exception du bloc |
| 8 | une petite classe qui ajoute un comportement par héritage |
| 9 | préférer la composition |
| 10 | `@dataclass(slots=True)` |

## Transfert vers le projet

Cas 3 : `src/mobilis/facturation.py`.

- Une ABC `Tarification` avec deux implémentations : `TarifOccasionnel` et
  `TarifAbonnement`. La méthode concrète de prix est partagée, seule
  l'application du plafond journalier change.
- `Decimal` pour tous les montants.
- Des dataclasses figées pour les barèmes et les abonnements.
