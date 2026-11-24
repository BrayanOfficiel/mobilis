# mobilis

Bibliothèque Python commune pour les données du réseau de vélos Mobilis
(projet du cours PYA-701, Python avancé) : référentiel des stations, trajets,
facturation et état des bornes.

État : cas 1 (référentiel des stations) traité.

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
mobilis stations            # bilan du référentiel
mobilis stations --detail   # une ligne par anomalie
```

```python
from pathlib import Path
from mobilis.stations import lire_stations

rapport = lire_stations(Path("kit/donnees/stations.csv"))
len(rapport.exploitables)   # 141
rapport.par_type()          # Counter des anomalies
```

`lire_stations` ne s'arrête pas à la première erreur : les lignes
inutilisables sont écartées et consignées dans le rapport avec leur numéro de
ligne.

## Décisions sur les données

Détail et chiffres dans [docs/journal_anomalies.md](docs/journal_anomalies.md).

- Code station présent deux fois : on garde la mise en service la plus récente.
- Capacité ou coordonnées absentes : la ligne est écartée.
- Latitude et longitude inversées : corrigées quand l'échange ramène le point
  dans l'agglomération.

## Qualité

```bash
pytest
mypy src tests
ruff check . && ruff format --check .
```

Les exercices du cours sont dans `exercices/` (`pytest exercices/module1`).
