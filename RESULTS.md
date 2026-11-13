# Résultats matériels du 12 novembre 2026

## Incident papier à exclure des mesures de limite

Papier rose, imprimante branchée en USB selon Marvin. Un premier essai a rencontré
`0x01` ; Marvin a signalé un blocage papier. Il est classé non concluant.

Un nouvel essai `single-pause` a envoyé 2590 lignes à énergie 14500, délai 14 ms,
puis marqué la pause de 10 s prévue au milieu de la deuxième trame. Le premier
`0x04` est reçu 9,682 s après le début de cette pause. Dernier état avant le défaut :
`00 0b 29`, premier état en défaut : `04 0c 29`. La télémétrie est enregistrée avec
trames complètes et CRC validé. Le processus s'arrête sur le défaut.

Marvin précise ensuite qu'environ une moitié de la **première** bande est sortie,
avec bruit d'impression mais sans progression du papier. Le voyant rouge est actif.
Il n'y a donc pas de preuve de 1,5 bande réellement imprimée. Le nombre exact de
lignes physiquement imprimées est inconnu. Ce résultat reproduit `0x04`, mais
l'incident d'entraînement empêche d'en déduire un seuil d'impression normal.

Le test `low-energy` prévu ensuite a été annulé pendant son attente de disponibilité,
avant tout envoi de raster. Il ne constitue pas un essai de l'énergie 4000.

Marvin a vérifié le rouleau, le passage du papier et le capot. Un contrôle court
`paper_check.py` est préparé : avance seule de 80 pas, mire de 160 lignes avec
repères tous les 40, puis avance de 80 pas. L'entraînement réel doit être confirmé
avant de reprendre les deux longues bandes.

Le contrôle court s’est terminé avec `flags=0x00` et le code de sortie 0.
Marvin confirme ensuite que le papier avance et que la mire est régulière.
Le test de faible énergie est relancé après cette confirmation.

## Faible énergie, entraînement vérifié, contrôle de débit actif

Énergie 4000, délai 14 ms, aucune pause fixe, deux bandes identiques. Résultat :
3453 lignes envoyées, aucun `0x04`, aucune demande XOFF, aucun temps d’attente de
flux. État final `00 0d 29` après 60 s supplémentaires d’observation, code de sortie 0.
Marvin confirme d’abord deux bandes complètes et régulières d’environ 21,6 cm,
puis précise que l’image est trop pâle pour contrôler sa géométrie. La longueur
semble correcte approximativement ; l’absence de compression dans l’image n’est
pas prouvée. Le résultat établit l’absence de `0x04` sur cet essai, sans valider une
qualité d’image exploitable, la répétabilité ou un seuil optimal.

## Énergie 14500, même cadence, contrôle de débit actif

Même entrée, délai 14 ms, sans pause fixe. XOFF à 1694 lignes envoyées, attente de
8,534 s jusqu’à XON, puis reprise. Premier `0x04` à 2539 lignes envoyées, soit 811
lignes envoyées dans la deuxième trame, 49,093 s après le début du premier job.
Marvin indique d’abord une avance régulière jusqu’au voyant rouge, puis corrige
ce constat après examen de l’image : le tirage a aussi des défauts d’avance.
L’arrêt `0x04` est confirmé, mais l’intégrité du déplacement papier ne l’est pas.

Le défaut est reproduit malgré le respect du contrôle de débit, avec des défauts
d’avance constatés sur le tirage. Le défaut du transport et la mise en défaut énergétique ne
sont pas équivalents. La comparaison 4000/14500 à pixels et délai constants renforce
une dépendance à la charge énergétique ; elle ne mesure ni température ni courant
et n’identifie pas à elle seule le composant responsable.

Le scénario `slow-cadence` a été annulé pendant le repos, avant toute impression,
à la suite de cette correction. Les comparaisons de cadence restent à faire.

## Passage aux mires de mesure

L’image à 14500 est décrite comme réduite à environ la moitié de la taille attendue.
La faible visibilité du tirage 4000 empêche une comparaison précise des détails.
`calibration.py` produit donc deux mires de 400 lignes : A peu chargée, B dense.
Chaque mire a cinq repères numérotés 0, 10, 20, 30, 40, espacés de 80 lignes.
La distance du repère 0 au repère 40 devrait être 40 mm à 8 points/mm.
Ce sont des repères pour mesure humaine, pas une mesure intégrée au matériel.
Les essais prévus gardent le même délai de 14 ms et le contrôle de débit actif,
à énergie 14500 puis 8000 pour une comparaison plus lisible que 4000.

## Mires courtes à 14500

Mire A : 400 lignes, 6955 points noirs. Mire B : 400 lignes, 91999 points noirs.
Deux jobs consécutifs, énergie 14500, délai 14 ms, aucune pause fixe et aucune
demande XOFF. 800 lignes envoyées, aucun défaut en fin de jobs ni pendant les 60 s
suivantes. Marvin confirme environ 4 cm entre les repères 0 et 40 sur A comme B,
sans compression visible. La géométrie est donc correcte sur ces tirages courts,
y compris la mire dense ; cela ne valide pas un tirage prolongé à cette énergie.
Le test suivant reprend les deux photos originales à énergie 8000.

## Photos à énergie 8000, délai 14 ms

Les deux photos originales sont envoyées sans pause fixe, contrôle de débit actif.
3453 lignes, 772736 points noirs, aucun XOFF, aucun `0x04` pendant l’envoi ou les
60 s supplémentaires d’observation. Code de sortie 0. Marvin confirme une image
lisible avec des proportions correctes sur les deux bandes.

Ce résultat est meilleur que le tirage trop pâle à 4000 et que le tirage comprimé
puis arrêté à 14500. Il ne constitue pas un seuil universel. Une répétition identique
est lancée avant de tester une cadence plus lente à 14500.

## Répétition à énergie 8000

Deuxième essai identique : 3453 lignes, aucune demande XOFF, aucun `0x04`, état
final `00 0c 29` après 60 s de surveillance supplémentaire. Les deux essais ont
chacun commencé après 60 s continues d’état `0x00`. Cela représente deux paires
séparées, pas quatre bandes imprimées d’un seul flux continu. Marvin confirme
également deux bandes lisibles à la bonne taille et sans défaut d’avance sur cette répétition.

Le scénario à énergie 14500 et délai 28 ms est ensuite lancé, toujours sans pause
fixe et avec le contrôle de débit actif.

## Énergie 14500 avec délai doublé à 28 ms

Même paire de photos, même énergie, contrôle de débit actif. Aucune demande XOFF.
Premier `0x04` à 1728 lignes envoyées, au contrôle de fin de la première trame,
51,520 s après le début du premier job. La deuxième bande n’est pas envoyée.
Le défaut est donc reproduit sans saturation signalée de la réception BLE.
La géométrie physique de ce dernier tirage n’a pas été confirmée.

## Bilan et réglage retenu pour ces essais

| Entrée | Énergie AF | Délai/ligne | Résultat matériel et logiciel |
| --- | ---: | ---: | --- |
| Deux photos | 4000 | 14 ms | 3453 lignes sans défaut, mais image trop pâle pour valider la géométrie |
| Deux photos, deux essais séparés | 8000 | 14 ms | 2 × 3453 lignes sans défaut ; les deux paires confirmées lisibles et aux bonnes proportions par Marvin |
| Deux photos | 14500 | 14 ms | 0x04 après 2539 lignes envoyées et 49,093 s ; 8,534 s d’attente XOFF/XON respectée ; compression visible sur papier |
| Deux photos | 14500 | 28 ms | 0x04 après 1728 lignes envoyées et 51,520 s ; aucune demande XOFF |
| Mires A et B courtes | 14500 | 14 ms | 800 lignes sans défaut ; dimensions de 4 cm confirmées sur les deux repères 0–40 |

Les deux essais à 8000 réussissent sans pauses fixes à l’intérieur des bandes ou
entre elles, avec une minute d’état clair avant chaque paire et une minute
supplémentaire d’observation après. Ce ne sont pas quatre bandes en flux continu.
Le contrôle de débit AE reste obligatoire ; le prototype précédent l’ignorait.
Il est maintenant partagé entre le banc et les commandes d’impression courantes.

La dépendance à l’énergie et à la durée du tirage est observée. La protection
thermique est une hypothèse cohérente avec la documentation de la famille
(`0x04` = tête chaude), mais nous ne mesurons ni température ni courant et ne
prouvons pas le mécanisme physique exact. La valeur maximale utilisable, les
séries plus longues, les autres papiers et l’autonomie sur batterie restent à tester.

Réglage retenu sur ce papier pour ces deux photos : énergie 8000, délai 0,014 s,
pas de pauses fixes, contrôle de débit actif. Ne pas utiliser le seul `--strength 1`
pour le reproduire : il choisit un autre délai par défaut.

```sh
.venv/bin/python experiment.py mid-energy private/01.png private/02.png --address UUID --execute
```

Pour `tile-send`, utiliser `--energy 8000 --row-delay 0.014 --chunk-rows 0
--cooldown 0 --feed-rows 80`. L’avance de 80 pas et le surcoût des fins/débuts de
jobs font partie du protocole d’essai, même en l’absence de pause volontaire.

Les fichiers sources et ce bilan sont commités localement dans `develop`. Aucun
remote GitHub ni aucune publication n’ont été créés. Les images et traces brutes
restent dans les dossiers ignorés. À la fin des essais, l’imprimante est en défaut
`0x04` après le scénario à 14500/28 ms ; aucun tirage automatique ne reste en attente.
