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

1. Choisir, déposer ou coller une photo dans l’atelier. Le collage fonctionne avec
   une image présente dans le presse-papiers, comme dans l’onglet Test.
2. Choisir le sens d’assemblage et le dimensionnement : nombre de tickets, largeur
   finale en cm, ou hauteur finale en cm. Les proportions de la photo sont conservées.
3. Ajuster le préréglage et les corrections. L’aperçu se recalcule automatiquement
   après 350 ms sans modification ; les réponses périmées sont écartées. Le bouton
   Original permet de comparer avec la source. Aucun fichier de bande n’est créé
   pendant ces changements : seul un petit aperçu est calculé en mémoire.
4. Télécharger le ZIP, ou cliquer **Imprimer la série** lorsque le papier est prêt.
   Ces actions préparent les PNG de 384 points et le manifeste sur disque. Une
   série déjà préparée est réutilisée tant que ses réglages ne changent pas.
5. En cas d’arrêt, vérifier le papier et l’état puis utiliser **Reprendre les bandes
   restantes**. L’URL contient l’identifiant de la série : la conserver permet de
   retrouver l’aperçu et l’avancement après rechargement ou redémarrage du service.

Modifier un réglage rend la série précédente périmée et désactive l’impression
jusqu’à la fin du nouvel aperçu. **Arrêter l’envoi** annule la transmission ;
les données déjà reçues par l’imprimante peuvent encore produire du papier.
Après rechargement, une série préparée reste exportable et reprenable. Pour changer
son rendu, il faut recharger la photo : le fichier source n’est pas conservé.

### Dimensions et longueur des tickets

La largeur utile est de 384 points, soit environ **48 mm à 8 points/mm**. En découpe
verticale avec N tickets, la largeur finale vaut `48 × N` mm et la longueur de chaque
ticket vaut `48 × N × hauteur_source / largeur_source` mm. En découpe horizontale,
la hauteur finale vaut `48 × N` mm et la longueur imprimée de chaque ticket vaut
`48 × N × largeur_source / hauteur_source` mm ; les bandes sont tournées pour l’envoi.

Une largeur ou hauteur finale saisie est convertie au point le plus proche, soit
0,125 mm. L’autre dimension suit le ratio de la source, après orientation EXIF et
recadrage éventuel. Le nombre de tickets est calculé automatiquement. Si le dernier
ticket n’est pas entièrement occupé, il est complété en blanc : l’interface indique
la marge à couper. Exemple : une largeur de 20 cm en vertical demande cinq tickets,
dont le dernier porte 8 mm d’image et 40 mm de blanc.

Les dimensions sont théoriques : l’avance du moteur, le papier et le patinage peuvent
modifier le résultat physique. L’avance finale de dégagement ajoute aussi du papier
au-delà de la longueur d’image annoncée. Les agrandissements n’ajoutent pas de détails
à une petite source ; le facteur d’agrandissement est affiché.

### Réglages photo et réglages matériels

Les préréglages Portrait, Net, Équilibré, Contraste fort et Trame reprennent les valeurs
de netteté, contraste, luminosité et algorithme du studio TinyPOS. Ils restent
modifiables individuellement. Sont également disponibles le gamma, le recadrage des
marges blanches et une force de rendu de 1 à 7. Cette dernière est une compensation
logicielle de luminosité : 1 éclaircit de 18 %, 7 ne compense pas, avec un pas de 3 %.
Ces sept niveaux sont distincts ; ils ne commandent pas la tête thermique.

Les quatre algorithmes sont Floyd–Steinberg, Atkinson, Bayer et seuil sans diffusion.
L’aperçu, limité à 1400 pixels de côté, illustre le rendu et les découpes ; le motif
de tramage à cette échelle ne reproduit pas chaque point du PNG final. Les PNG du
ZIP donnent le raster réellement envoyé, sans guides bleus de découpe.

L’énergie, le délai par ligne et la pause entre tickets sont séparés, dans les
réglages d’impression repliés. Ils démarrent à **6000 / 14 ms / aucune pause fixe**.
Ces valeurs de départ sont partagées avec les impressions classiques du bridge. Les valeurs
explicites des séries déjà préparées restent conservées : une série à 8000 reste
à 8000 tant que l’utilisateur ne prépare pas une nouvelle série avec un autre réglage.
Deux champs permettent aussi de tester une pause à l’intérieur d’un ticket : le
nombre de lignes entre pauses et leur durée. Le nombre de lignes démarre à **0**,
donc ces pauses restent désactivées par défaut. Par exemple, 400 lignes / 6 secondes
interrompt l’envoi tous les 5 cm théoriques, sans refermer la trame. L’atelier utilise
des intervalles fixes ; l’option CLI de recherche d’une ligne claire reste distincte.
Les arrêts peuvent laisser des traits et leur efficacité doit être vérifiée sur
papier. Les valeurs sont conservées dans le manifeste et lors de la restauration.
Changer l’énergie ne modifie pas l’aperçu : son effet dépend du papier et du matériel,
et n’est pas simulé. Les essais à 13000 et 14500 ont rencontré des défauts sur notre
exemplaire. Un tirage très sombre a également déclenché `0x04` à 8000 : ce réglage
ne garantit donc pas l’absence de défaut. Voir `RESULTS.md`. Le réglage classique de force TinyPOS garde son
comportement propre ; la nouvelle échelle de compensation concerne cet atelier.

## Réutilisation du pilote et des fonctions existantes

- Le rendu web est dans `photo_bands.py` : dimensions exactes, corrections, aperçu
  réduit et bandes imprimables. Le CLI garde ses options historiques : son `--mm`
  arrondit toujours au multiple supérieur de 48 mm. Les deux rendus ne sont donc pas
  interchangeables point par point.
- L’impression appelle `print_series` et son état `state.json`, avec le même
  `transport.py` et le contrôle de débit AE.
- Les impressions classiques TinyPOS sont redirigées vers `print_image` du même
  pilote, avec énergie 6000 et délai 14 ms. Le niveau de rendu de TinyPOS reste
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
| `POST /api/internal/bands/preview` | Aperçu en mémoire (data URL PNG), dimensions et paramètres ; ne crée pas de série |
| `POST /api/internal/bands/prepare` | Prépare et sauvegarde les PNG, l’aperçu et le manifeste ; retourne l’identifiant |
| `GET /api/internal/bands/{id}` | Paramètres préparés, statut et bandes envoyées |
| `GET /api/internal/bands/{id}/preview` | Aperçu PNG |
| `GET /api/internal/bands/{id}/download` | ZIP des bandes, de l’aperçu et du manifeste |
| `POST /api/internal/bands/{id}/print?resume=false` | Mise en attente de l’envoi ; `resume=true` reprend l’avancement |
| `POST /api/internal/bands/{id}/cancel` | Annulation de la série active ou en attente |

Les deux routes POST acceptent un multipart : `file`, `direction` (vertical/horizontal),
`size_mode` (count/width/height), `count`, `size_mm` (pour width/height), `preset`,
`dither`, `sharpness`, `contrast`, `brightness`, `gain`, `strength`, `autocrop`,
`energy`, `row_delay`, `cooldown`, `chunk_rows`, `chunk_pause`. `chunk_rows=0` désactive
les pauses internes ; `chunk_pause` vaut 6 secondes par défaut. `gain` désigne le gamma et `strength` la compensation
logicielle, indépendante de l’énergie. Un préréglage fournit les valeurs omises de
netteté, contraste, luminosité et tramage ; les valeurs explicites les remplacent.

La source est limitée à 20 Mo et 20 millions de pixels. La limite arbitraire de
20 tickets est supprimée. Une bande reste limitée à 12 000 lignes (150 cm) et la
série à 200 000 lignes, tous tickets réunis. Ces budgets de calcul sont vérifiés
avant allocation du raster final : ce ne sont pas des capacités physiques validées
de l’imprimante. Le nombre autorisé dépend donc du format et du ratio de la source.
Les identifiants
sont générés côté serveur ; les chemins de fichiers fournis par le client ne sont
jamais utilisés pour charger un document du Mac.

## Vérification

```sh
TINYPOS_PATH=/chemin/TinyPOS-Bridge .venv/bin/python -m unittest -v
```

Sans `TINYPOS_PATH`, les tests API optionnels sont ignorés ; les tests du runtime
et du pilote restent disponibles. La suite vérifie notamment les refus d’accès,
le cookie amont forgé, les entrées invalides, les aperçus sans fichiers, les dimensions
exactes, les marges blanches verticales et horizontales, les corrections et le ZIP, la sérialisation,
l’appel du pilote, l’annulation et la reprise après interruption. Le transport
est simulé : ces tests n’impriment pas et ne prouvent pas l’avance physique.

Le parcours navigateur a été vérifié sur image synthétique : sélection et collage,
aperçu automatique, changement de préréglage, 21 tickets, largeur de 20 cm, ZIP et
restauration par URL, sur bureau et à 390 px. Le ZIP a été relu pour vérifier ses
dimensions et la marge blanche. L’envoi réel par l’API web a ensuite été contrôlé
sur les deux premières bandes de la photo sombre : défaut d’énergie à 6000, délai
14 ms, aucune pause, bitmaps identiques aux originaux. Le propriétaire confirme
les deux bandes lisibles, longues de 28,8 cm et sans écrasement ; les 60 secondes
de surveillance finale restent sans défaut. Voir `RESULTS.md` pour les mires et
la portée matérielle de ces essais. La série complète de six bandes reste non testée.
Le précédent profil à 8000 avait passé deux paires de photos, mais a échoué sur
le nouveau contenu très sombre.
