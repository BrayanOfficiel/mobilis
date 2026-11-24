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

- les stations écartées (MB-0028, MB-0090, MB-0109) apparaissent dans les
  trajets : tranché au cas 2, voir plus bas ;
- l'emprise utilisée pour détecter les inversions (latitude 44 à 47,
  longitude 3 à 6) est volontairement large, elle n'est pas un contrôle de
  position précis.

## trajets_2026-08_2026-10.csv.gz

Reproduire : `mobilis frequentation --detail`. Fichier gzip, UTF-8, séparateur
`,`, 155 631 lignes de données, aucune ligne illisible. Le fichier n'est pas
trié (bornes hors réseau qui envoient en retard), ce qui ne gêne pas
l'agrégation.

| Anomalie | Nombre | Décision | Justification |
|---|---:|---|---|
| Date en UTC (`...Z`) | 22 772 dates | converti | Instant non ambigu. |
| Date `JJ/MM/AAAA HH:MM:SS` sans fuseau | 10 293 dates | lu en heure de Paris | Les trajets voisins au format ISO montrent que c'est l'heure locale (départ 00:04+02:00, arrivée "01/08/2026 00:42:17"). Aucune de ces dates ne tombe dans l'heure ambiguë du 25/10 (02:00 à 02:59). |
| Trajet transmis deux fois (même `trajet_id`) | 620 | écarté (R11) | Les deux lignes sont identiques et toujours consécutives. Dédoublonnage sur une fenêtre des 1 000 derniers identifiants : mémoire bornée. |
| Fin antérieure au début | 143 | écarté (R10) | Écart de 1 à 59 minutes : impossible de savoir laquelle des deux dates est fausse. 2 autres étaient aussi des doublons. |
| Station absente du référentiel (MB-0998, MB-0999) | 111 | gardé, signalé (R12) | Le trajet a eu lieu ; on ne sait pas ce que sont ces stations. |
| Ni station ni heure d'arrivée | 78 | gardé | Le départ est réel et compte dans la fréquentation ; pas d'arrivée. Non-restitution pour la facturation (R9). |
| Distance absente | 4 705 | gardé | La distance ne sert pas aux cas 2 et 3. |

Pas des anomalies : 46 854 trajets sans `abonne_id` (usagers occasionnels,
R3).

Les stations MB-0028, MB-0090 et MB-0109, écartées du référentiel faute de
capacité ou de coordonnées, apparaissent dans les trajets : elles ne sont
pas signalées comme inconnues (elles sont bien dans `stations.csv`) et
comptent dans la fréquentation.

Résultat : 154 868 trajets retenus sur 92 jours (65 de semaine, 27 de
week-end).

Mémoire : pic de 2,7 Mio sur le fichier réel (`mobilis --mesure
frequentation`), il ne dépend que du nombre de stations, d'heures et de
jours. `test_memoire_constante` vérifie qu'un fichier 5 fois plus gros ne
fait pas monter le pic de plus de 10 %.

Limites : les jours fériés (15 août) sont comptés comme des jours ordinaires ;
un doublon séparé de plus de 1 000 lignes de l'original ne serait pas vu.
