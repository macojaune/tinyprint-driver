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

Les fonctions de découpe et d’assemblage sont encore dans le prototype. Leur
séparation du transport/protocole est prévue avant une publication éventuelle.
Les photos personnelles et journaux bruts restent ignorés dans `private/` et `runs/`.

## Provenance et publication

Référence utilisée pour comprendre le protocole :
https://github.com/sajjad-amin/TinyPOS-Bridge

Aucune licence racine n’a été trouvée dans le checkout de cette référence lors
de l’initialisation. L’audit de provenance, l’attribution et le choix de licence
restent à terminer avant de publier ce dépôt. Aucune publication GitHub à ce stade.
