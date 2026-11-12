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
