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
