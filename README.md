# Tiny Print driver

Pilote expérimental Python 3.10+ (essayé sous Python 3.13) pour une mini imprimante BLE Tiny Print X5.
Développement et mesures sur macOS ; compatibilité des autres modèles non vérifiée.

Le pilote est repris du travail local `tools/tinyprint_cli.py` de cette session,
initialement développé à côté d’un clone de TinyPOS-Bridge.

## Installation

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tinyprint_cli.py scan
.venv/bin/python tinyprint_cli.py status --address UUID
```

Le bit d’état `0x04` est associé à un arrêt d’impression constaté. Sa cause et la
signification des autres octets sont en cours d’investigation. Les noms internes
`overheat` et `temp` sont historiques, pas des diagnostics matériels confirmés.

`protocol.py` contient le codec et les commandes, sans dépendance à BLE ou aux images.
`transport.py` gère la session BLE, les notifications et le contrôle de débit AE.
`tinyprint_cli.py` contient les commandes utilisateur et les fonctions de découpe du prototype.
Leur séparation complète reste prévue avant une publication éventuelle.
Les photos personnelles et journaux bruts restent ignorés dans `private/` et `runs/`.

Le banc de tests matériels et les hypothèses sont décrits dans `EXPERIMENTS.md`.
`python -m unittest -v` vérifie le codec et le banc sans accéder à l'imprimante.

## Provenance et publication

Référence utilisée pour comprendre le protocole :
https://github.com/sajjad-amin/TinyPOS-Bridge

Aucune licence racine n’a été trouvée dans le checkout de cette référence lors
de l’initialisation. L’audit de provenance, l’attribution et le choix de licence
restent à terminer avant de publier ce dépôt. Aucune publication GitHub à ce stade.

## Paramètres indépendants

`--energy` remplace seulement la valeur AF, et `--row-delay` seulement le délai
entre lignes en secondes. Le seuil de rendu reste celui de `--strength`.

```sh
python tinyprint_cli.py image image.png --energy 8000 --row-delay 0.014 --chunk-rows 0 --address UUID
```

Le réglage énergie 8000 / délai 14 ms sans pauses fixes a passé deux essais de
deux bandes sur notre exemplaire X5, avec contrôle visuel de Marvin. Ce résultat
ne garantit pas les autres papiers, modèles ou séries plus longues.
Le contrôle de débit `AE 10`/`AE 00` reste actif même si `--chunk-rows 0` désactive
les pauses fixes. Une fin d'envoi et un état `0x00` ne prouvent pas la bonne géométrie
sur papier ; le bilan matériel est dans `RESULTS.md`.
