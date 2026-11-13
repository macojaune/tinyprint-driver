# Tiny Print driver

Piloter une mini imprimante thermique depuis son ordinateur, sans passer par
l’application Tiny Print : texte, images monochromes, photos tramées et images
réparties sur plusieurs bandes de papier.

Le projet contient un codec de protocole indépendant, une session Bluetooth Low
Energy avec contrôle de débit, un CLI et un banc d’essais matériels. Il s’agit d’un
prototype testé sur **un exemplaire X5 sous macOS**, pas d’un pilote universel.
Le dépôt est [public sur GitHub](https://github.com/macojaune/tinyprint-driver),
avec le développement sur `develop`. Il est distribué sous [licence MIT](LICENSE).

## L’imprimante de référence

Identification relue sur l’appareil le **12 novembre 2026**, via `info` :

| Élément | Identification et niveau de preuve |
| --- | --- |
| Nom Bluetooth | **X5**, lu lors de la connexion BLE |
| Chaîne firmware | **E1.3.5.3**, réponse réelle à la commande A8 |
| Identifiant de marque / référence commerciale | **Inconnus** : le propriétaire confirme l’absence de toute étiquette |
| Application utilisée auparavant | **Tiny Print**, indiqué par le propriétaire |
| Connecteur | **Micro-USB**, confirmé par le propriétaire ; ce modèle n’est pas identifié comme un C15 USB-C |
| Transport utilisé | Bluetooth Low Energy ; aucune impression USB validée |
| Largeur de trame testée | **384 points**, 48 octets par ligne |
| Échelle de travail | Environ **8 points/mm**, soit 48 mm imprimables ; repères de 40 mm contrôlés sur papier |
| Service principal | `0000ae30-0000-1000-8000-00805f9b34fb` |
| Écriture raster/commandes | `0000ae01-0000-1000-8000-00805f9b34fb`, write without response |
| Notifications état et contrôle de débit | `0000ae02-0000-1000-8000-00805f9b34fb` |
| Service supplémentaire observé | `0000ae3a-0000-1000-8000-00805f9b34fb`, usage non établi |

Réponse A8 enregistrée :

```text
51 78 a8 01 0a 00 45 00 03 31 2e 33 2e 35 2e 33 a9 ff
```

La chaîne affichable `E1.3.5.3` est extraite du payload, qui contient aussi deux
octets non imprimables. Ce n’est pas une image du firmware : aucun firmware n’a
été extrait, décompilé ou remplacé. Le MCU et le fabricant ne sont pas identifiés.
Le câble USB n’a pas fourni de voie d’impression lors des investigations ; cela
ne prouve pas que les lignes de données du connecteur sont absentes du circuit.

## Modèles apparentés : candidats, pas compatibilités certifiées

Les références commerciales varient et certains noms sont réutilisés pour des
protocoles différents. Cette liste recense les familles trouvées dans les sources
ci-dessous ; elle n’est ni exhaustive ni une promesse de fonctionnement ici.

| Modèles / noms | Preuve disponible | Statut dans ce dépôt |
| --- | --- | --- |
| X5, exemplaire décrit ci-dessus | Connexion, trames, impressions et essais physiques | **Testé sur macOS**, avec les limites du bilan matériel |
| GB01, GB02, GB03, GT01, GT02, YHK-A133, MX06, MX10 | Registre `PRINTER_CAT` de [Thermal_Printer](https://github.com/bitbank2/Thermal_Printer/blob/master/src/Thermal_Printer.cpp) | Famille candidate ; aucun de ces exemplaires testé ici |
| YT01, MX05, MX08, MXTP | Modèles déclarés par [NaitLee/Cat-Printer](https://github.com/NaitLee/Cat-Printer/blob/main/README.md), projet signalé comme historique par son auteur | Candidats externes, à identifier et valider individuellement |
| Autres X5 | Nom cité par [opuu/cat-printer](https://github.com/opuu/cat-printer), sans preuve d’identité avec notre carte | Même nom insuffisant pour garantir les mêmes réglages |
| C15, X6, X7 et autres noms reconnus par le scan | Heuristiques de découverte présentes dans le prototype | **Pas une validation** de protocole ou de matériel |

Pour un autre appareil : relever les services GATT et les réponses A3/A8, vérifier
le framing et la largeur raster, puis tester une petite mire avant un long tirage.
Le seul nom de l’app mobile, la forme du boîtier ou un préfixe `51 78` ne suffit pas.
Les familles ESC/POS, PeriPage, Paperang, Phomemo, MXW01, etc. ne sont pas déclarées
compatibles par ce dépôt : leur pilote éventuel doit être identifié séparément.

## Installation

Python **3.10+** est requis ; les essais ont utilisé Python **3.13** sur macOS.
`requirements.txt` fixe les versions testées de Bleak et Pillow. Linux et Windows
restent à valider sur matériel ; les commandes de shell ci-dessous sont pour
macOS / un shell Unix.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tinyprint_cli.py --help
```

Les commandes `pdf` utilisent en plus PyMuPDF, non installé par les dépendances de
base : `python -m pip install PyMuPDF`. Le PDF est une fonction secondaire du
prototype, pas une garantie de lisibilité des documents grand format réduits.

Sur macOS, autoriser l’accès Bluetooth de l’application qui lance Python si le
système le demande. Allumer l’imprimante et libérer la connexion de l’app mobile
avant de se connecter depuis l’ordinateur.

## Identifier son imprimante sans imprimer

```sh
python tinyprint_cli.py scan
python tinyprint_cli.py info --address ADRESSE_DU_SCAN
python tinyprint_cli.py status --address ADRESSE_DU_SCAN
```

Remplacer `ADRESSE_DU_SCAN` par l’adresse renvoyée sur son propre ordinateur.
Sur macOS, la valeur observée est un UUID CoreBluetooth ; elle n’est pas une
référence commerciale à recopier depuis un autre Mac. Vérifier le nom annoncé à
la connexion. Une adresse explicite introuvable arrête la connexion ; aucun autre candidat
n’est sélectionné à sa place.

`scan`, `info` et `status` n’envoient pas de raster et ne font pas avancer le papier.
`status` renvoie actuellement 0 si le bit 0x04 est absent, 3 s’il est actif et 1 si
la lecture échoue. Lire aussi les flags : un code 0 seul ne certifie pas tous les
capteurs ni la qualité de l’impression.

## Préparer un aperçu, puis imprimer

Choisir explicitement son fichier. Une commande `image` imprime sauf si
`--no-print` est présent ; `--preview` seul ne désactive pas l’impression.

```sh
mkdir -p private
python tinyprint_cli.py image mon-image.jpg --dither floyd --gain 1.2 --preview private/apercu.png --no-print
```

Exemples de tirages réels, une fois le papier prêt :

```sh
python tinyprint_cli.py text "Bonjour" --energy 8000 --row-delay 0.014 --chunk-rows 0 --address ADRESSE_DU_SCAN
python tinyprint_cli.py image mon-image.jpg --dither floyd --energy 8000 --row-delay 0.014 --chunk-rows 0 --address ADRESSE_DU_SCAN
```

`--dither` propose `none`, `floyd`, `atkinson` et `bayer`. `--gain` agit sur le
rendu. `--energy` remplace seulement la valeur AF et `--row-delay` seulement le
délai entre lignes en secondes. `--strength` couple énergie, délai et seuil de
rendu ; il ne faut pas l’utiliser seul pour reproduire un profil de test précis.
Les valeurs AF sont des unités de protocole, pas des joules mesurés.

## Imprimer une grande photo en bandes

Le besoin initial : préparer des tickets longs à assembler, avec découpe verticale
ou horizontale, ordre explicite et reprise après interruption.

Export sans impression, trois bandes verticales :

```sh
python tinyprint_cli.py tile mon-image.jpg --dir vertical --count 3 --outdir private/bandes --dither floyd --preview private/assemblage.png
```

`--dir horizontal` prépare des bandes tournées pour exploiter la largeur de la
tête ; le manifeste indique la rotation pour l’assemblage. `--flat` désactive ce
retournement. Chaque fichier fait 384 points de large. Le dossier contient les
PNG numérotés, `manifest.json` et un script d’impression généré.

`--mm` demande une taille physique sur l’axe de découpe : le nombre de bandes est
arrondi au multiple supérieur de 48 mm. Par exemple, 300 mm donnent 7 bandes,
soit environ 336 mm. Ce n’est pas encore une mise à l’échelle physique exacte.
`--gap` concerne la planche d’assemblage ; l’avance papier réelle est réglée par
`--feed-mm` ou `--feed-rows`.

Pour envoyer une série préparée avec les paramètres des essais à 8000 :

```sh
python tinyprint_cli.py tile-send private/bandes/manifest.json --energy 8000 --row-delay 0.014 --chunk-rows 0 --cooldown 0 --feed-rows 80 --address ADRESSE_DU_SCAN
```

Ajouter `--resume` pour reprendre les bandes non terminées selon `state.json`.
Une fin d’envoi n’est pas une mesure de la longueur papier. Si un ticket est
physiquement raté malgré un état clair, vérifier son avancement avant de reprendre.
Le script généré et les métadonnées du manifeste ne doivent pas être supposés
rejouer automatiquement tous les overrides : passer les paramètres explicitement.

## Réglage éprouvé et limites matérielles

Sur notre X5, avec les deux photos de test et le papier rose : **8000 / 14 ms**,
sans pauses fixes, a passé **deux essais de deux bandes**. Les deux paires ont été
confirmées lisibles, de bonne taille et sans défaut d’avance par le propriétaire.
Chaque essai commençait après 60 s d’état clair et était surveillé 60 s après
l’envoi. Quatre bandes d’un seul flux et les autres papiers ne sont pas validés.

À 4000, le tirage est trop pâle pour valider précisément la géométrie. À 14500,
`0x04` apparaît même avec le délai doublé à 28 ms. À 13000 / 14 ms, le nouveau
contrôle échoue également sur `0x04`. Les compteurs détaillés, observations papier
et essais exclus pour blocage mécanique sont dans [RESULTS.md](RESULTS.md).

`--chunk-rows` et `--chunk-pause` permettent des pauses fixes internes. Par défaut,
le prototype conserve 400 lignes / 6 s ; ce réglage historique n’a pas suffi sur
une paire de longues bandes. `--chunk-rows 0` supprime ces pauses, pas le contrôle
de débit. Les pauses peuvent laisser des traits sur papier.

## Protocole, état et récupération

```text
51 78 CMD DIR LEN_LO LEN_HI PAYLOAD... CRC8 FF
```

CRC-8 : polynôme 0x07, initialisation 0, sans réflexion ni XOR final. Longueur sur
16 bits little-endian. Pour notre exemplaire : ligne raster A2 de 48 octets,
bits LSB-first, 1 = noir ; énergie AF sur 16 bits little-endian.

| Commande | Usage dans notre implémentation |
| --- | --- |
| A3 / A8 | État / identification firmware |
| A4 / AF | Qualité / énergie |
| BD / BE | Paramètres de début de job ; leur sémantique exacte peut varier selon la famille |
| A6 | Début et fin de trame lattice |
| A2 | Ligne raster brute |
| A1 | Avance papier |
| AE 10 / AE 00 reçus | Suspendre les écritures / reprendre |

**Respecter AE est indispensable** : un premier prototype ignorait XOFF. Le banc
et le CLI utilisent maintenant la même session de transport, avec une notification
persistante. Le protocole de référence est décrit dans le [wiki Thermal_Printer](https://github.com/bitbank2/Thermal_Printer/wiki/Cat-Rabbit-printer-info).

La documentation de cette famille associe 0x01 au capteur papier/porte, 0x02 au
capot, 0x04 à une tête chaude et 0x08 à une batterie faible. Ici, 0x01 a accompagné
un incident papier et 0x04 des arrêts rouges. Le mécanisme physique exact de 0x04
reste à déterminer : pas de mesure directe de température ou de courant.
Les noms internes `temp`, `overheat` et `paper` sont historiques ; les octets 2/3
restent bruts et ne doivent pas être interprétés comme °C ou % de batterie.

Arrêter l’envoi en cas de défaut, vérifier l’entraînement, puis relire l’état avant
reprise. Le retour spontané a pris plusieurs minutes avec une durée variable.
Après un redémarrage manuel, une lecture a confirmé 0x00, sans prouver que le
redémarrage est l’unique cause de la récupération ni que le défaut ne récidivera
pas. Aucun reset firmware par commande n’a été identifié. `--force` n’est pas une
méthode de récupération : le transport garde ses propres arrêts sur défaut.

## Structure et reprise par un agent

| Fichier | Responsabilité |
| --- | --- |
| `protocol.py` | Codec et constantes, sans Bleak ni Pillow |
| `transport.py` | Session BLE, notifications, état et contrôle de débit |
| `tinyprint_cli.py` | Commandes utilisateur, rendu et découpe du prototype |
| `experiment.py` | Scénarios matériels reproductibles, dry-run par défaut |
| `paper_check.py`, `calibration.py` | Contrôle court d’avance / génération de mires |
| `test_*.py` | Tests logiciels du codec, du transport et du chemin CLI |
| [EXPERIMENTS.md](EXPERIMENTS.md) | Méthode, variables et hypothèses |
| [RESULTS.md](RESULTS.md) | Résultats et corrections des observations humaines |
| [AGENT_PROMPT.md](AGENT_PROMPT.md) | Prompt à copier et personnaliser pour un agent |

```sh
python -m unittest -v
```

Ces tests ne reproduisent pas l’échauffement ni le patinage réel du papier.
`experiment.py` affiche son scénario sans Bluetooth tant que `--execute` est
absent. Les scénarios à deux photos nécessitent les deux bitmaps monochromes de
384 points choisis par l’utilisateur ; les photos personnelles ne sont pas fournies.
`python calibration.py` crée deux mires synthétiques dans `private/calibration/`,
sans connexion ni impression.

Une extension web locale est disponible : voir [WEB_BRIDGE.md](WEB_BRIDGE.md).
Elle ajoute l’atelier photo à l’interface du clone TinyPOS-Bridge, qui reste un projet
séparé. Son code et ses accès locaux ne sont pas recopiés dans ce dépôt.
Les fonctions spécifiques d’assemblage sont encore dans le CLI ; leur séparation
complète du pilote générique reste une étape de préparation à la publication.

## Provenance, publication et contributions

Références consultées : [TinyPOS-Bridge](https://github.com/sajjad-amin/TinyPOS-Bridge),
[wiki du protocole](https://github.com/bitbank2/Thermal_Printer/wiki/Cat-Rabbit-printer-info),
[PythonCatPrinter](https://github.com/WerWolv/PythonCatPrinter),
[Cat-Printer](https://github.com/NaitLee/Cat-Printer).
Le travail local a d’abord été développé à côté du clone TinyPOS-Bridge, puis
isolé dans ce dépôt Git.

Ce projet est distribué sous [licence MIT](LICENSE), copyright 2026 macojaune.
Les références ci-dessus documentent les travaux et sources de protocole consultés.

Les dossiers `private/`, `runs/` et `.venv/`, ainsi que les fichiers d’environnement,
sont ignorés. Les manifestes générés peuvent contenir un chemin absolu de source :
les relire avant de les partager. Pour ajouter une compatibilité, documenter le
nom BLE, les services, la version A8, les réglages et les contrôles physiques ;
un modèle reconnu par le scan seul reste un candidat.
