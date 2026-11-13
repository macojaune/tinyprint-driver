# Résultats matériels du 12 novembre 2026

## Complément : défaut à 8000 sur une photo très sombre

Une série web de six bandes horizontales carrées de 28,8 × 28,8 cm a rencontré
`0x04`, avec énergie 8000, délai 14 ms et aucune pause fixe. Le rendu utilisait
Atkinson, netteté 2,5, contraste 1,22, luminosité 1,05, gamma 1 et force logicielle 4.
Les six PNG sauvegardés font chacun 384 × 2304 points. Leur conversion en lignes
de 48 octets et en paquets A2 conserve bien les 2304 lignes ; aucune réduction de
moitié n’a été observée dans ce chemin logiciel.

Le journal indique 2304 lignes envoyées pour la première bande, puis un état A3
clair. Le défaut `0x04` apparaît pendant la deuxième bande, après le repère de
600 lignes. Aucun XOFF n’est consigné. L’état de reprise conserve la première
bande dans `done`, ce qui signifie ici envoi et contrôle A3 terminés, sans preuve
de bonne avance physique. Ne pas considérer ce ticket comme validé sur papier.

Marvin décrit un tirage de moins de 15 cm, saccadé, dont il ne peut pas identifier
précisément la partie manquante. La photo est abstraite et sombre. L’absence du
bas reconnaissable de la photo entière ne suffit pas à identifier une troncature
de la première bande : en découpe horizontale, celle-ci ne contient que le haut.
La compression, la perte de lignes et l’exécution retardée ne sont pas départagées.

La première bande contient 785398 points noirs, soit 88,77 % de couverture, et sa
fenêtre de 400 lignes la plus dense atteint 97,93 %. C’est légèrement plus de
points noirs que les deux bandes réunies des anciens essais réussis à 8000
qui totalisaient 772736 points noirs. Ce compte ne mesure ni température ni
puissance, mais montre que les charges des deux expériences sont différentes.
8000 ne constitue donc pas un réglage universel évitant le défaut.

Une lecture ultérieure a trouvé l’état clair `00 0d 29`. Une mire claire distincte,
384 × 2304 points, a ensuite été envoyée par le bridge avec énergie 8000 et délai
14 ms, sans pause. Marvin confirme 28 cm entre ses repères 0 et 280 mm, régulièrement
espacés. L’échelle est donc correcte sur ce tirage long peu chargé. Il observe
également une avance plus rapide sur les contenus clairs que sur les contenus sombres.
Le résultat du tirage sombre ne se déduit pas de cette réussite.

À la demande de Marvin, la même mire est répétée avec un fond noir et une couverture
de 89,90 %, en conservant 384 × 2304 points, les repères, énergie 8000, délai 14 ms
et aucune pause. L’état initial est clair. Les 2304 lignes sont envoyées, puis le
contrôle A3 final reçoit `0x04`, environ 37,5 s après la demande d’impression. La
bande reste non terminée dans l’état de reprise. Ce scénario reproduit donc le
défaut sur une seule longue bande sombre, sans le rendu Atkinson de la photo.
Marvin voit le repère 0 puis 20 à la bonne distance, mais les repères suivants se
tassent, et le repère final 280 est présent à une mauvaise distance. Sa photo montre
la mire claire longue et régulière, suivie de la mire sombre fortement comprimée.
Il ne s’agit donc pas seulement d’une coupure avant la fin du contenu. L’avance
effective devient insuffisante sous cette charge ; la mesure de la longueur totale
et la distinction entre mécanisme d’entraînement, alimentation et exécution firmware
restent ouvertes. Cette expérience ne mesure ni chauffe, ni tension, ni courant.

### Même mire sombre, pauses internes 400 lignes / 6 secondes

Le tirage commence après 60 secondes continues d’état A3 clair. Le raster et
l’énergie 8000 restent identiques, avec un délai de 14 ms et cinq pauses de six
secondes, exactement après 400, 800, 1200, 1600 et 2000 lignes. Les états aux pauses
sont clairs. Le premier `0x04` enregistré arrive après l’envoi des 2304 lignes,
environ 67,9 s après le début du raster. La trame reçue est valide au CRC :
`51 78 a3 01 03 00 04 0c 28 8f ff`. Aucun XOFF n’est reçu pendant cet essai.

Marvin mesure environ **13 cm entre 0 et 280 mm**, au lieu de 28 cm. Les graduations
commencent encore à se tasser vers 20–25 mm, avant la première pause prévue à 50 mm
théoriques. Ces pauses ne corrigent donc ni le défaut final ni la géométrie sur
cette mire. Elles ne sont pas un profil validé pour les photos très sombres.

### Mode de dessin : essai isolé sans correction de la géométrie

Le pilote hérite de TinyPOS une commande `BE 01` nommée `CMD_APPLY_ENERGY`.
La [documentation de cette famille](https://github.com/bitbank2/Thermal_Printer/wiki/Cat-Rabbit-printer-info)
et le [code primaire de Thermal_Printer](https://github.com/bitbank2/Thermal_Printer/blob/master/src/Thermal_Printer.cpp)
l’identifient comme un mode de dessin, 1 pour le texte et 0 pour les images.
Un essai isolé avec `BE 00` utilise les 800 premières lignes de la même mire sombre,
soit 10 cm théoriques, à énergie 8000, délai 14 ms et sans pause. Il commence après
60 secondes continues d’état clair. Aucun défaut n’est enregistré pendant l’envoi
ou les 60 secondes d’observation qui suivent. Marvin confirme toutefois que les
graduations se tassent encore après 20–25 mm.

Ce changement de mode seul ne résout donc pas la géométrie. La réussite du contrôle
A3 sur ce tirage court ne valide ni sa longueur physique ni une longue bande.
Le pilote normal conserve son mode hérité ; aucune correction du mode n’est livrée
sur la base de cet essai.

### Mire sombre courte à énergie 6000

Les mêmes 800 premières lignes sont ensuite envoyées à énergie **6000**, en
revenant au mode hérité `BE 01`, avec délai 14 ms et sans pause. Le départ suit
60 secondes continues d’état clair. Aucun défaut n’apparaît pendant l’envoi ni
durant les 60 secondes d’observation suivantes. Marvin confirme **8 cm entre les
repères 0 et 80 mm**, réguliers et plutôt lisibles. L’alimentation reste le même
port USB du Mac.

La baisse d’énergie rétablit donc la géométrie sur cette mire sombre courte. Cela
ne distingue pas un effet thermique, électrique ou une adaptation du firmware ;
ces mécanismes ne sont pas mesurés.

La mire sombre complète de 2304 lignes est ensuite envoyée à 6000 avec les mêmes
paramètres, après 60 secondes continues d’état clair. L’envoi et les 60 secondes
de surveillance suivantes se terminent sans défaut, état final `00 0c 29`. La
mesure physique est confirmée par Marvin : **28 cm réguliers et lisibles entre
les repères 0 et 280 mm**. Cette mire dense longue valide donc sa géométrie sur
ce papier à 6000. Le rendu sur la photo est contrôlé séparément.

### Première bande de la photo à 6000

Le premier PNG du tirage raté est réutilisé sans changement de pixels : 384 × 2304
points, 785398 points noirs. À énergie 6000, délai 14 ms, mode hérité et sans pause,
après 60 secondes continues d’état clair, l’envoi et les 60 secondes de surveillance
se terminent sans défaut. L’état final est `00 0d 29`. Marvin confirme **28,8 cm,
image lisible et sans écrasement**.

Le bridge retient donc 6000 / 14 ms sans pauses fixes comme nouveau profil de départ
pour cet exemplaire et ce papier. La valeur est partagée entre l’atelier et les
impressions classiques du bridge. Les paramètres explicites des anciennes séries
restent conservés ; les profils `--strength` du CLI ne sont pas modifiés. Cette
réussite sur une bande ne valide pas encore la série entière de six tickets.

### Deux premières bandes consécutives via le bridge livré

Après livraison de la nouvelle énergie par défaut à 6000, les deux premiers bitmaps d’origine
sont préparés et envoyés via l’API du serveur local. Le paramètre d’énergie est
volontairement omis ; le manifeste reçoit bien 6000 / 14 ms, sans pause interne
ni entre les tickets. Les PNG préparés sont vérifiés identiques, pixel pour pixel,
aux deux fichiers du tirage raté, chacun de 384 × 2304 points.

Le départ suit 60 secondes continues d’état clair. Les deux bandes sont envoyées
et marquées terminées. Aucun défaut n’est enregistré pendant l’envoi ni les
60 secondes de surveillance qui suivent, état final `00 0d 28`. Marvin confirme
**deux bandes d’environ 28,8 cm chacune, lisibles et sans écrasement**, y compris
sur la deuxième. Le profil 6000 / 14 ms est donc validé pour cette paire sur ce
papier et cet exemplaire, en plus de la mire dense et de la première bande isolée.
Le contrôle de la série complète est décrit ci-dessous.

### Série de six : premier arrêt causé par une fin de rouleau

La première tentative de six bandes à 6000 s’arrête au contrôle de fin de la
première bande, après 2304 lignes envoyées, avec `0x01`. Aucune bande n’est marquée
terminée ; la deuxième n’est pas lancée par le pilote. Marvin décrit une avance
devenue difficile en fin de ticket, puis confirme que le rouleau était terminé.
Il n’avait pas ouvert le capot pendant l’envoi. Une lecture ultérieure retourne
encore `01 1b 28`. Cet incident de consommable ne mesure pas la limite thermique
du profil à 6000.

### Série de six sur un nouveau rouleau : géométrie correcte, lisibilité insuffisante

Après chargement d’un nouveau rouleau, le `0x01` disparaît. Le tirage reprend depuis
la première bande, après 60 secondes continues d’état clair. Les six PNG sont
vérifiés identiques aux originaux : 13824 lignes, 2806584 points noirs, énergie
6000, délai 14 ms, aucune pause fixe interne ni entre tickets. L’envoi par l’API
dure environ 219 secondes et termine les six bandes. Aucun défaut pendant l’envoi
ni les 60 secondes de surveillance suivantes ; état final `00 0d 28`.

Marvin confirme six bandes correctes en dimensions et régularité, mais **peu
lisibles**. La couleur et le type du nouveau rouleau ainsi que la nature précise
du défaut de rendu restent à préciser. L’envoi continu et la géométrie des six
bandes sont donc confirmés sur cet essai ; la qualité du rendu reste à améliorer.
Ne pas transformer ce résultat en validation complète de lisibilité sur tout papier.

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

## Contrôle après redémarrage manuel

Marvin redémarre l’imprimante et constate la disparition apparente du défaut.
La lecture BLE effectuée ensuite, sans impression, confirme `flags=0x00`, payload
`00 0d 29`, avec un code de sortie 0. Le défaut n’est donc plus signalé après ce
redémarrage. Nous n’avons pas effectué de lecture immédiatement avant le redémarrage
ni chronométré l’intervalle : cette observation ne distingue pas formellement
l’effet du redémarrage d’une récupération spontanée pendant le même intervalle.
Elle ne prouve ni le refroidissement de la tête ni l’absence de récidive à 14500.
Aucune nouvelle impression n’est lancée.

## Essai à 13000 / 14 ms après redémarrage

Même paire de photos, mêmes pixels, pas de pause fixe et contrôle de débit actif.
État clair vérifié pendant 60 s avant le démarrage. XOFF à 2428 lignes envoyées,
attente de 6,308 s jusqu’à XON, puis reprise. Premier `0x04` à 2548 lignes envoyées,
dont 820 dans la deuxième trame. Le processus s’arrête avec le code 3 ; aucune
nouvelle impression automatique n’est programmée. La géométrie et la longueur
réellement imprimées de cet essai restent à confirmer par le propriétaire.
13000 n’a donc pas évité le défaut sur cet essai. Cela ne mesure pas la valeur
maximale utilisable entre 8000 et 13000.

## Identification actualisée pour la documentation

Après le test, une lecture `info` sans impression confirme le nom X5, les services
AE30 et AE3A, TX AE01, notifications AE02 et la réponse firmware :
`51 78 a8 01 0a 00 45 00 03 31 2e 33 2e 35 2e 33 a9 ff`, chaîne `E1.3.5.3`.
L’état reçu au même moment est `04 0d 29`. Le propriétaire confirme que l’appareil
ne comporte aucune étiquette ; fabricant et référence commerciale restent inconnus.
