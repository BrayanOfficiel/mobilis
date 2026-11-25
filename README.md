# mobilis

Bibliothèque Python commune pour les données du réseau de vélos Mobilis
(projet du cours PYA-701, Python avancé) : référentiel des stations, trajets,
facturation et état des bornes.

État : les cinq cas sont traités (stations, trajets, facturation, état en temps
réel, commande `mobilis`).

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Données

Les fichiers du kit ne sont pas versionnés. Le dossier des données se donne
par l'option `--donnees`, sinon par la variable `MOBILIS_DONNEES`, sinon
`kit/donnees` est utilisé.

```bash
export MOBILIS_DONNEES=/chemin/vers/mobilis-kit/donnees
```

## Utilisation

```bash
mobilis stations                      # bilan du référentiel
mobilis stations --detail             # une ligne par anomalie
mobilis frequentation                 # profil horaire, stations qui se vident
mobilis frequentation --mois 2026-10  # un seul mois
mobilis --mesure frequentation        # + durée et pic mémoire
mobilis facturation                   # chiffre d'affaires par mois et formule
mobilis facturation --detail          # + abonnés introuvables à signaler
mobilis etat                          # état des stations via l'API des bornes
mobilis etat --comparer               # séquentiel, threads et asyncio mesurés
```

`mobilis etat` interroge l'API des bornes (simulateur du kit :
`python kit/outils/serveur_bornes.py`). La clé n'est pas dans le dépôt : elle
se donne par `--cle` ou par la variable `MOBILIS_API_CLE`, l'adresse par
`--url` ou `MOBILIS_API_URL` (défaut `http://127.0.0.1:8765`).

```python
from pathlib import Path

from mobilis.journal import Journal
from mobilis.stations import lire_stations
from mobilis.trajets import TypeJour, analyser_trajets

rapport = lire_stations(Path("kit/donnees/stations.csv"))
len(rapport.exploitables)  # 141

journal = Journal()
freq = analyser_trajets(
    Path("kit/donnees/trajets_2026-08_2026-10.csv.gz"), journal, rapport.codes_lus
)
freq.profil_horaire(TypeJour.SEMAINE)  # [(heure, départs/jour, arrivées/jour), ...]
journal.compteurs  # anomalies rencontrées
```

```python
from mobilis.abonnes import lire_abonnes
from mobilis.facturation import facturer_fichier, lire_tarifs

donnees = Path("kit/donnees")
abonnes = lire_abonnes(donnees / "abonnes.jsonl", Journal())
tarifs = lire_tarifs(donnees / "tarifs.json")
facturation = facturer_fichier(
    donnees / "trajets_2026-08_2026-10.csv.gz", tarifs, abonnes, Journal(), rapport.codes_lus
)
facturation.ca.total("2026-10")  # Decimal('93879.80')
```

Le fichier des trajets est lu par une chaîne de générateurs (lecture,
conversion, dédoublonnage, filtres) puis agrégé : il n'est jamais chargé en
mémoire.

## Décisions sur les données

Détail et chiffres dans [docs/journal_anomalies.md](docs/journal_anomalies.md).

- Code station présent deux fois : on garde la mise en service la plus récente.
- Capacité ou coordonnées absentes : la station est écartée du référentiel.
- Latitude et longitude inversées : corrigées quand l'échange ramène le point
  dans l'agglomération.
- Date de trajet sans fuseau : heure de Paris.
- Trajet en double : écarté (fenêtre des 1 000 derniers identifiants).
- Fin avant le début : trajet écarté.
- Trajet sans arrivée : le départ compte, pas d'arrivée.
- Station absente de `stations.csv` : trajet gardé et signalé.
- Ligne d'abonné coupée : gardée si identifiant, formule et dates sont
  entiers, sinon écartée (ses trajets passent au tarif occasionnel).
- Trajet à cheval sur deux jours : il compte pour le jour local de son début.
- Montants en `Decimal` de bout en bout, arrondis au centime (moitié vers le
  haut).

La tarification est une classe abstraite `Tarification` (calcul du prix
commun) avec deux implémentations : `TarifOccasionnel` (sans plafond) et
`TarifAbonnement` (plafond journalier par abonné).

Pour l'API des bornes, le décorateur `@reessayer` (et `@reessayer_async`)
refait un appel en 429, 503, 504 ou erreur réseau, en respectant
`Retry-After`. Le client ne laisse jamais plus de 8 requêtes en vol. Une
borne qui ne répond pas est signalée sans arrêter la photo des autres.

## Qualité

```bash
pytest                       # 90 tests, ceux qui lisent le kit sont ignorés sans lui
pytest --cov                 # couverture des lignes et des branches
mypy src tests               # mode strict
ruff check . && ruff format --check .
pytest exercices             # exercices du cours
```

Les tests n'ont besoin ni du kit ni du serveur des bornes. `tests/conftest.py`
fabrique un petit kit aux mêmes formats (cp1252, gzip, lignes abîmées), et
l'API est simulée par `unittest.mock`. Les exemples E1 à E6 de la
spécification sont un test paramétré (`tests/test_facturation.py`).

La CI (`.github/workflows/qualite.yml`) lance ruff, mypy et pytest sous
Python 3.11, 3.12 et 3.13. `pre-commit install` lance le formatage, le lint
et mypy avant chaque commit.

## Organisation du code

```
src/mobilis/
  stations.py      cas 1 : Station (dataclass figée), Statut, rapport d'anomalies
  trajets.py       cas 2 : Trajet, chaîne de générateurs, Frequentation
  abonnes.py       cas 3 : périodes d'abonnement, formule active à une date
  facturation.py   cas 3 : tarifs en Decimal, Tarification (ABC) et ses 2 implémentations
  bornes.py        cas 4 : @reessayer, clients de l'API, photo du réseau
  journal.py       compteurs d'anomalies
  decorateurs.py   @mesure (temps, pic mémoire), @tolerante (écarte et journalise)
  cli.py           commande mobilis
docs/journal_anomalies.md   chaque anomalie : nombre, décision, justification
```
