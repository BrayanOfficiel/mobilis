# Journal des anomalies

Chaque chiffre se reproduit avec `mobilis stations --detail` sur les fichiers
bruts du kit. Aucun fichier n'est modifié à la main.

## stations.csv

Format constaté : encodage cp1252 (vieil outil Windows), fins de ligne CRLF,
séparateur `;`, décimales à virgule, 153 lignes de données pour 150 codes.

| Anomalie | Lignes | Décision | Justification |
|---|---:|---|---|
| Statut écrit de 7 façons (`En service`, `en_service`, `EN SERVICE`, `HS`, `FERMEE`...) | 153 | normalisé | Les graphies désignent clairement 3 états, ramenés à l'Enum `Statut`. Un statut hors de cette liste ferait écarter la ligne. |
| Espaces en trop autour d'un champ (nom, capacité, statut) | 37 | corrigé | Aucun sens métier, simple bruit de saisie. |
| Date de mise en service au format AAAA-MM-JJ au lieu de JJ/MM/AAAA | 6 | corrigé | Format non ambigu, la date est sûre. |
| Latitude et longitude inversées (MB-0064, MB-0135) | 2 | corrigé | Le point tombe hors de l'agglomération, l'échange l'y ramène exactement. Une seule lecture possible. |
| Capacité `NC` (MB-0028, MB-0090) | 2 | écarté | Impossible de savoir si une station est pleine sans sa capacité ; inventer une valeur fausserait le cas 4. |
| Coordonnées absentes (MB-0109) | 1 | écarté | Station impossible à placer. |
| Code présent deux fois (MB-0033, MB-0068, MB-0104) | 3 | écarté (la plus ancienne) | Même nom et mêmes coordonnées, seules la capacité, le statut et la date changent : une remise en service après travaux. On garde la date la plus récente. |

Résultat : 147 stations retenues, dont 141 exploitables (en service), 3 hors
service et 3 fermées.

Une ligne peut porter plusieurs anomalies (espaces et doublon par exemple) :
le total des anomalies n'est donc pas le nombre de lignes touchées.

Points non tranchés :

- les stations écartées (MB-0028, MB-0090, MB-0109) apparaîtront sans doute
  dans les trajets : à compter comme "station inconnue du référentiel" ou à
  garder hors référentiel, à décider au cas 2 ;
- l'emprise utilisée pour détecter les inversions (latitude 44 à 47,
  longitude 3 à 6) est volontairement large, elle n'est pas un contrôle de
  position précis.
