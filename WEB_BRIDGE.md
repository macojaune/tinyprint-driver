# Atelier photo dans TinyPOS-Bridge

Cette extension combine l’interface existante de TinyPOS et le moteur de
`tinyprint-driver`. Elle ajoute **Atelier photo en bandes** au menu, sans modifier
les fichiers du clone TinyPOS. Le serveur reste sur le Mac à `127.0.0.1`.

## Lancer

Prérequis : un clone séparé de
[TinyPOS-Bridge](https://github.com/sajjad-amin/TinyPOS-Bridge). L’intégration a été
vérifiée avec son commit `860d3b7`. Ses conditions de licence restent celles de
son auteur ; ce dépôt fournit seulement l’extension et le pilote.

Dans le dépôt tinyprint-driver :

```sh
.venv/bin/python -m pip install -r requirements-web.txt
.venv/bin/python web_bridge.py --tinypos-path /chemin/TinyPOS-Bridge --address ADRESSE_DU_SCAN
```

Ouvrir **http://127.0.0.1:8100/photo-bands** et se connecter avec le compte admin
TinyPOS déjà configuré dans le clone. Si une session précédente est rejetée,
repasser par `/login` : l’extension ajoute sa propre session après authentification.
`--port` permet de choisir un autre port si un serveur utilise déjà 8100.
Sans `--address`, la préparation et le ZIP fonctionnent, mais l’impression est
refusée. Aucun scan ni tirage n’est lancé par la préparation.

Au premier lancement, le serveur copie la base TinyPOS par sauvegarde SQLite vers
`private/web-bands/tinypos.db`. La base originale reste inchangée. Les réglages et
identifiants du clone restent la source de configuration. Les modifications faites
ensuite dans cette copie ne sont pas synchronisées vers la base d’origine.
`--data-dir` change ce dossier. Le serveur est local : l’accès depuis le téléphone
ou une autre machine n’est pas activé par cette commande.

## Utilisation

1. Choisir une photo, le sens d’assemblage et le nombre de tickets.
2. Choisir le tramage et la luminosité. Les réglages d’impression sont repliés ;
   ils démarrent à énergie 8000, délai 14 ms et sans pause fixe entre tickets.
3. Cliquer **Préparer les bandes**. L’aperçu, les dimensions, les longueurs et l’ordre
   apparaissent. Aucune impression n’a lieu à ce stade.
4. Télécharger le ZIP, ou cliquer **Imprimer la série** lorsque le papier est prêt.
5. En cas d’arrêt, vérifier le papier et l’état puis utiliser **Reprendre les bandes
   restantes**. L’URL contient l’identifiant de la série : la conserver permet de
   retrouver l’aperçu et l’avancement après rechargement ou redémarrage du service.

Modifier un réglage rend l’aperçu précédent périmé et désactive l’impression
jusqu’à une nouvelle préparation. **Arrêter l’envoi** annule la transmission ;
les données déjà reçues par l’imprimante peuvent encore produire du papier.
La largeur utile et les limites de taille restent celles du CLI : environ 48 mm
par ticket sur l’axe de découpe, pas encore une taille finale physique exacte.

## Réutilisation du pilote et des fonctions existantes

- Le rendu utilise `slice_image`, `strip_to_print`, `dither` et `assemble` du CLI.
- L’impression appelle `print_series` et son état `state.json`, avec le même
  `transport.py` et le contrôle de débit AE.
- Les impressions classiques TinyPOS sont redirigées vers `print_image` du même
  pilote, avec énergie 8000 et délai 14 ms. Le niveau de rendu de TinyPOS reste
  transmis ; sa sélection de force ne choisit plus seule l’énergie matérielle.
- Un verrou partagé sérialise les séries, les impressions classiques et l’avance
  papier du processus serveur. Le bouton d’arrêt classique atteint l’envoi actif.
- La CLI reste indépendante : éviter de lancer un tirage CLI pendant un tirage web,
  car le verrou ne traverse pas plusieurs processus.
- Les séries ont leur propre avancement dans l’atelier ; elles ne sont pas ajoutées
  à l’historique des jobs classiques TinyPOS. Leur URL et leur manifeste sont les
  points de reprise. Le mode relais distant n’est pas pris en charge pour les séries.

## API locale utilisée par l’interface

Toutes ces routes nécessitent une session admin TinyPOS et la session additionnelle
émise par l’extension après la connexion. Les mutations vérifient l’Origin lorsqu’il
est présent. Les anciennes clés d’API TinyPOS ne remplacent pas cette session pour
les nouvelles routes. Les API classiques restent celles du clone.

| Méthode et route | Fonction |
| --- | --- |
| `POST /api/internal/bands/prepare` | Multipart : `file`, `direction`, `count`, `dither`, `gain`, `energy`, `row_delay`, `cooldown` |
| `GET /api/internal/bands/{id}` | Paramètres préparés, statut et bandes envoyées |
| `GET /api/internal/bands/{id}/preview` | Aperçu PNG |
| `GET /api/internal/bands/{id}/download` | ZIP des bandes, de l’aperçu et du manifeste |
| `POST /api/internal/bands/{id}/print?resume=false` | Mise en attente de l’envoi ; `resume=true` reprend l’avancement |
| `POST /api/internal/bands/{id}/cancel` | Annulation de la série active ou en attente |

La préparation accepte au maximum 20 Mo, 20 millions de pixels et 20 bandes.
Une bande est limitée à 12 000 lignes et la série à 60 000 lignes. Les identifiants
sont générés côté serveur ; les chemins de fichiers fournis par le client ne sont
jamais utilisés pour charger un document du Mac.

## Vérification

```sh
TINYPOS_PATH=/chemin/TinyPOS-Bridge .venv/bin/python -m unittest -v
```

Sans `TINYPOS_PATH`, les tests API optionnels sont ignorés ; les tests du runtime
et du pilote restent disponibles. La suite vérifie notamment les refus d’accès,
le cookie amont forgé, les entrées invalides, les aperçus, le ZIP, la sérialisation,
l’appel du pilote, l’annulation et la reprise après interruption. Le transport
est simulé : ces tests n’impriment pas et ne prouvent pas l’avance physique.

Le parcours navigateur a été vérifié sur image synthétique : upload, préparation
verticale et horizontale, aperçu, dimensions, invalidation des réglages et ZIP,
aux largeurs 1280 px et 390 px. L’impression web réelle reste à valider avec le
propriétaire et le papier prêt. Le profil 8000/14 ms vient des essais physiques
antérieurs du CLI décrits dans `RESULTS.md`.
