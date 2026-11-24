# mobilis

Bibliothèque Python commune pour les données du réseau de vélos Mobilis
(projet du cours PYA-701, Python avancé) : référentiel des stations, trajets,
facturation et état des bornes.

État : cas 1 (référentiel des stations) et cas 2 (trajets) traités.

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
```

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

## Qualité

```bash
pytest
mypy src tests
ruff check . && ruff format --check .
```

Les exercices du cours sont dans `exercices/` (`pytest exercices/module1`).
