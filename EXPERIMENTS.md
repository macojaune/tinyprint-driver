# Recherche du défaut 0x04

Le verdict matériel est la notification A3 contenant le bit `0x04`, associé aux
arrêts de papier constatés par Marvin. Les tests unitaires du banc ne remplacent
pas cette reproduction matérielle.

## Hypothèses et prédictions

1. Charge liée à l'énergie : si elle est déterminante, passer de 14500 à 4000,
   sans modifier les pixels ni les délais, devrait repousser ou supprimer le défaut.
   Un succès ne distingue pas encore chauffe de tête et alimentation/batterie.
2. Charge liée à la cadence : à énergie et pixels constants, doubler le délai entre
   lignes devrait repousser le défaut si le débit ou le cycle de fonctionnement compte.
   Ce changement affecte aussi le temps de refroidissement entre lignes.
3. Durée d'activité ou charge cumulée : une pause unique de 10 s après 2590 lignes
   devrait permettre la suite si cette durée de repos suffit. Un défaut avant
   2590 lignes signifie que cette pause est placée trop tard pour cet état initial.

## Protocole commun

- Deux mêmes trames monochromes de 384 points, 1728 puis 1725 lignes.
- Empreintes SHA-256 et nombre de points noirs enregistrés pour contrôler l'entrée.
- Papier rose, imprimante X5 branchée en USB d'après Marvin.
- Chaque essai commence après 60 s continues d'état `0x00`. Ce critère ne mesure
  ni la température initiale ni la charge de batterie ; l'état interne peut différer.
- Un job par bande, avance de 80 lignes entre jobs. Pas de pause volontaire entre
  bandes ; les commandes de fin, d'avance, de début et la lecture d'état prennent
  néanmoins du temps. « Sans pause » ne signifie donc pas un unique job continu.
- Télémétrie A3 toutes les 100 lignes, sans attendre les réponses pendant le raster.
  Cette instrumentation ajoute des commandes BLE. Elle diffère des anciens essais
  qui lisaient l'état seulement aux pauses et en fin de bande.
- Arrêt au premier `0x04` reçu, ou résultat inconclusif en cas d'erreur de connexion
  ou d'absence d'état frais aux points de contrôle obligatoires.
- Les compteurs désignent des lignes envoyées, pas une longueur imprimée mesurée.
- Après une mise en défaut, le banc attend le retour à `0x00` et 60 s stables avant
  l'essai suivant. Il ne force pas un reset et ne réémet pas une bande automatiquement.

## Scénarios

| Nom | Énergie AF | Délai demandé/ligne | Pause interne | Pause volontaire entre bandes |
| --- | ---: | ---: | --- | ---: |
| single-pause | 14500 | 14 ms | 10 s à la ligne 862 de la bande 2 | 0 s |
| low-energy | 4000 | 14 ms | aucune | 0 s |
| baseline | 14500 | 14 ms | aucune | 0 s |
| slow-cadence | 14500 | 28 ms | aucune | 0 s |

14500 et 4000 sont des valeurs du protocole, pas des joules mesurés. 14 ms est
le délai demandé au planificateur ; l'intervalle réel comprend aussi les écritures
BLE et les réveils de la boucle asyncio. Les horodatages permettent de le mesurer.

```sh
# Sans --execute : affiche le plan sans accéder au Bluetooth.
python experiment.py single-pause private/01.png private/02.png

# Tirage réel, une fois le rouleau prêt et l'impression autorisée.
python experiment.py single-pause private/01.png private/02.png --address UUID --execute
```

Les journaux bruts et les résultats JSON restent dans `runs/`, ignoré par Git.
Le bilan anonymisé est versionné après les essais. Une réussite sur une seule paire
ne garantit pas une limite universelle ; une répétition est nécessaire.
