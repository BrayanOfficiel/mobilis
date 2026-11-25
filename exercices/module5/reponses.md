# Module 5 : réponses

## TP panier (`panier.py`)

`article_le_plus_cher` utilise `max(..., default=None)` : pas de cas
particulier à écrire pour le panier vide, et le type de retour
`Article | None` oblige l'appelant (et mypy) à traiter ce cas. Les tests
couvrent le cas nominal, le panier vide et les remises hors bornes des deux
côtés (-1 et 150).

## Exercice 1 : palindrome (`exos.py`)

On met en minuscules et on retire tous les blancs (`"".join(texte.split())`)
avant de comparer au texte retourné. Le test paramétré couvre deux vrais
cas, la chaîne vide (palindrome par convention) et un faux.

## Exercice 2 : mock d'un dépôt

Deux tests avec `Mock` : un succès, où l'on vérifie que `save` est appelé
une fois avec l'article, et un échec, où `side_effect = OSError(...)` fait
lever `save`. Le message d'erreur est vérifié avec `caplog`. Le dépôt est
passé en paramètre, ce qui évite tout `patch`.

## Autocontrôles

1. Une fixture partagée que les tests modifient crée une dépendance entre
   les tests : le résultat change selon l'ordre d'exécution.
2. `monkeypatch` modifie temporairement une variable d'environnement, un
   attribut ou une entrée de dictionnaire, puis restaure tout à la fin du
   test.
3. `--strict-markers` refuse un marqueur non déclaré, une faute de frappe
   comme `@pytest.mark.lnet` fait alors échouer la collecte.
4. Là où elle est utilisée : on patche `mon_module.fonction`, pas
   `module_d_origine.fonction`.
5. La couverture des branches vérifie que les deux côtés de chaque `if` sont
   exécutés. Une ligne `if erreur: lever()` peut être couverte sans que le
   cas d'erreur ait jamais été testé.
6. Hypothesis réduit l'entrée à l'exemple le plus simple qui casse encore la
   propriété, puis le rejoue dans les exécutions suivantes.
7. Pour n'ignorer que cette erreur-là : une autre erreur sur la même ligne
   serait encore signalée.
8. Après le `return`, mypy sait que la variable est `str`.
9. La famille S contient des règles de sécurité issues de bandit : `eval`,
   mots de passe en dur, `subprocess` avec `shell=True`...
10. Le formateur supprime les débats de style : les revues portent sur le
    fond, et les diffs ne montrent que les vrais changements.
11. Avec la disposition `src`, les tests importent le paquet installé comme
    le feront les utilisateurs. Un fichier oublié dans le paquet ou une
    dépendance non déclarée se voient tout de suite.
12. Déclarer, c'est dire de quoi le code a besoin, avec des contraintes
    souples, dans `pyproject.toml`. Verrouiller, c'est figer les versions
    exactes installées partout (fichier lock).
13. La publication de confiance authentifie la CI auprès de PyPI sans jeton
    stocké à longue durée de vie.
14. Une bibliothèque ne configure pas la journalisation : c'est
    l'application qui choisit les niveaux et les destinations. Une
    bibliothèque qui la configure imposerait ses choix et dupliquerait les
    messages.
15. Plusieurs versions de Python dans la CI : une bibliothèque doit marcher
    sur les versions qu'elle annonce (`requires-python`), et la syntaxe ou
    la bibliothèque standard changent d'une version à l'autre.

## Quiz

| # | Réponse |
|---|---|
| 1 | son nom commence par `test_` |
| 2 | préparer un objet réutilisable injecté dans les tests |
| 3 | `with pytest.raises(...)` |
| 4 | imprécision des flottants |
| 5 | remplacer une dépendance externe |
| 6 | vérifier les types sans exécuter |
| 7 | `pyproject.toml` |
| 8 | éviter d'importer le code non installé |
| 9 | chaque ligne exécutée, pas tous les cas corrects |
| 10 | lancer format, lint et vérifications avant chaque commit |

## Transfert vers le projet

Cas 5, dans le dépôt :

- la commande `mobilis` et ses quatre sous-commandes ;
- les tests de `tests/`, dont E1 à E6 paramétrés et l'API des bornes simulée
  par `unittest.mock` ;
- mypy strict, ruff ;
- la CI GitHub Actions (`.github/workflows/qualite.yml`) ;
- la configuration pre-commit.
