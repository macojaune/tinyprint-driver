# Prompt de reprise et d’adaptation

Copier le texte ci-dessous dans un agent ayant accès au dépôt. Remplir l’objectif ;
les autres champs peuvent rester inconnus. Une autorisation d’impression ne se
déduit pas de la seule présence de cette fiche dans le dépôt.

---

Tu travailles dans le dépôt **Tiny Print driver**. Réalise l’objectif de
l’utilisateur à partir du pilote existant, avec des changements vérifiables.

## Demande à personnaliser

- **Objectif et résultat attendu :** [décrire ce que je veux obtenir]
- **Exemple concret d’utilisation :** [entrée → action → sortie attendue]
- **Ordinateur et système :** [macOS / Linux / Windows / inconnu]
- **Imprimante :** [nom BLE, version si connue, présence ou non d’une étiquette]
- **Contenu autorisé :** [mes fichiers explicitement désignés / texte fourni / mires synthétiques]
- **Forme souhaitée :** [CLI / script Python / interface / API / intégration / à préciser]
- **Impressions réelles autorisées :** [non / oui, papier prêt, quantité ou longueur maximale]
- **Livraison demandée :** [local et commits / publication explicitement précisée]

Si un champ manque, détermine ce que le dépôt permet déjà de savoir. Pose uniquement
les questions qui changent le résultat attendu ou bloquent une action matérielle ;
continue les travaux indépendants pendant l’attente. Une autorisation déjà donnée
pour le même périmètre reste valable. Au départ, si aucune impression réelle n’est
autorisée, prépare et vérifie le code sans envoyer de raster ni avancer le papier.

## 1. Établir la situation actuelle

1. Vérifie le répertoire, les consignes applicables, `git status --short --branch`,
   les remotes et les travaux existants. Préserve les modifications sans rapport.
2. Lis `README.md` pour l’installation, les commandes et l’identité du matériel de
   référence. Si tu touches au débit, à l’énergie, aux pauses, à la géométrie ou au
   support matériel, lis aussi `EXPERIMENTS.md` et `RESULTS.md`.
3. Inspecte le code au point d’entrée concerné et `--help`. Le contenu des documents
   décrit des observations datées ; vérifie l’état réel avant de t’y fier.
4. Reformule en quelques lignes le changement concret à réaliser et les critères
   observables de réussite. Reste dans le périmètre demandé.

Cette étape est terminée lorsque l’entrée, le comportement attendu, le matériel
cible et les limites d’intervention sont identifiés, ou que les seules inconnues
restantes sont nommées et isolées des travaux qui peuvent avancer.

## 2. Choisir le chemin qui répond au besoin

- **Texte, image ou nouveau rendu :** pars des commandes et du rendu dans
  `tinyprint_cli.py`. Prépare un aperçu avant une impression lorsqu’il permet de
  contrôler le résultat. Utilise les fichiers indiqués par l’utilisateur ou des
  fixtures synthétiques ; garde ses documents personnels hors des exemples publics.
- **Découpe et assemblage :** vérifie `slice_image`, le manifeste et `tile-send`.
  Contrôle l’ordre, la rotation et les dimensions. Le mode `--mm` arrondit actuellement
  au multiple de 48 mm ; une taille exacte nécessite un contrat de changement clair.
- **Autre application ou intégration :** réutilise `protocol.py` et `transport.py`.
  Introduis une interface graphique, un serveur ou un service permanent seulement
  lorsque l’objectif le demande. Le dépôt n’inclut pas le serveur du clone TinyPOS.
- **Nouvelle imprimante :** commence par la découverte et les lectures d’identification
  autorisées. Compare la carte GATT, les réponses A3/A8, le framing et la largeur
  raster. Ajoute un profil distinct si les commandes diffèrent. Le nom commercial
  ou le préfixe de trame ne suffit pas à établir une compatibilité.
- **Préparation d’une publication :** sépare le pilote générique et les usages
  spécifiques, vérifie les attributions/licences et les fichiers suivis. Les photos,
  adresses locales, manifestes privés et accès au bridge restent privés. Une demande
  de développement local n’autorise pas à publier un dépôt ou à pousser du contenu.

## 3. Préserver le contrat du matériel

Le matériel de référence s’annonce comme **X5**, chaîne firmware **E1.3.5.3**,
connecteur micro-USB selon son propriétaire, sans étiquette de marque. Relis sa
fiche dans le README plutôt que d’inventer un fabricant. Pour un autre utilisateur,
identifie son propre exemplaire et son adresse locale.

- Le codec est dans `protocol.py` ; les paquets observés utilisent CRC-8 et 384 points
  par ligne. L’énergie little-endian est vérifiée sur notre exemplaire seulement.
- La session partagée dans `transport.py` suspend les écritures sur **AE 10**, reprend
  sur **AE 00** et interrompt sur les bits d’erreur reconnus. Conserve la notification
  persistante et le contrôle de débit, y compris si les pauses fixes sont désactivées.
- Change un paramètre matériel à la fois pour une comparaison. `--strength` couple
  plusieurs paramètres ; préfère les overrides indépendants d’énergie et de délai.
- Les flags et les octets bruts sont les preuves à conserver. Les champs historiques
  `temp`, `overheat` et `paper` ne sont pas des mesures physiques calibrées.
- `0x04` a accompagné des arrêts rouges. Attends un état approprié avant reprise et
  vérifie l’entraînement en cas de papier immobile ou de compression. Un redémarrage
  a été suivi d’un état clair ; une commande de reset firmware reste inconnue.
- Le réglage conservateur testé sur deux paires de photos est décrit dans `RESULTS.md`.
  Adapte-le au papier et au matériel observés ; une réussite ne devient pas une
  garantie universelle, et un état clair ne prouve pas une bonne avance papier.

## 4. Implémenter et vérifier

Fais les modifications utiles au résultat demandé en conservant la séparation
codec / transport / rendu. Écris un test de régression au bon niveau si tu corriges
un comportement du transport ou du CLI. Les tests du faux transport peuvent prouver
le respect de XOFF/XON ; ils ne peuvent pas prouver l’absence de surchauffe ou de
patinage. Exécute les contrôles pertinents, dont `python -m unittest -v` pour ces
composants, et vérifie les exemples ou exports modifiés.

Pour une validation matérielle autorisée :

1. Vérifie que le bon appareil est sélectionné et que le rouleau est prêt. Le prototype
   peut retomber sur un autre candidat si l’adresse explicite est introuvable ;
   corrige ou borne ce comportement avant une utilisation sur plusieurs appareils.
2. Commence par une petite mire si l’appareil, le papier ou la géométrie a changé.
   Compare les repères imprimés à leur échelle attendue et confirme l’avance réelle.
3. Exécute le parcours demandé avec des paramètres et une entrée identifiés. Le banc
   `experiment.py` est en dry-run tant que `--execute` est absent. Consulte son aide
   et ses scénarios au lieu de recopier une ancienne commande privée.
4. Conserve les traces utiles dans `runs/`, sans les ajouter automatiquement à Git.
   Distingue lignes envoyées, état reçu et observations physiques. Surveille les
   défauts retardés après la fin de l’envoi.
5. Si le contrôle papier nécessite l’utilisateur, demande le constat précis et garde
   le résultat physique en attente jusqu’à sa réponse. Une correction humaine tardive
   remplace la conclusion antérieure ; mets le bilan à jour.

Un scénario matériel est validé seulement si le comportement attendu est observé
sur papier, avec la cible et les paramètres documentés. Si la validation est
impossible, livre le code vérifié et nomme exactement la partie non testée.

## 5. Livrer une reprise compréhensible

- Mets à jour le README pour un comportement visible changé, et le bilan matériel
  pour les nouvelles preuves ou corrections. Garde les hypothèses séparées des faits.
- Committe les changements du périmètre autorisé. Utilise l’organisation et les
  consignes Git applicables ; la branche locale ou l’existence d’un dépôt n’implique
  pas une publication GitHub.
- Termine par le résultat utilisateur, les contrôles réellement exécutés, les fichiers
  utiles, le commit et l’état exact de livraison. Identifie les limites restantes
  sans transformer un test synthétique, une écriture BLE ou un code de sortie 0 en
  preuve d’impression physique réussie.

---

Exemples d’objectifs à remplacer dans la fiche : imprimer des étiquettes depuis un
CSV choisi, générer des tickets à partir d’un texte, préparer une photo en bandes
à dimensions exactes, ajouter une API locale demandée, ou identifier une imprimante
candidate. Ces exemples ne déclenchent aucune réalisation supplémentaire à eux seuls.
