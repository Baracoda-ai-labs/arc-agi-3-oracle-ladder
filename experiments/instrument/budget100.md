# Test plafond « budget ×100 » (CW-305, nuit du 20 au 21/10, A) — 13 niveaux frontière, règles exactes

## 1. Question et prédiction
Thomas : « on a la matière pour aller 1 000 × plus vite ». Avant toute réécriture de l'état, on mesure ce que rapporterait ×100 **de temps**
(30 000 s au lieu de 300 s, sans plafond de nœuds), à règles exactes, sur les niveaux frontière. Lecture fixée d'avance (CW-305) :
un niveau qui tombe → la vitesse a de la valeur ; rien ne tombe → tout va au guidage. Prédiction de A (CCM-285-A) : le meilleur d'abord
s'arrêtera sur la **mémoire** (≈ 5 Go par million de nœuds), pas sur le temps.

## 2. Résultats (copie `648418b`, G allumé, `nice 10`, garde 8 Go par processus ; programmes d'AVANT la correction du budget de B)
| niveau | `but` (meilleur d'abord) | `sous_buts` (défi 6) | `profondeur` (clé seule) |
|---|---|---|---|
| dc22 N4 | **gagné, 74 s, 65 coups** | mémoire à 5 h 43 | **gagné, 3 476 s, 64 coups** (3,4 M nœuds) |
| ls20 N4 | — | — | **gagné, 513 s, 64 coups** (0,5 M nœuds) |
| g50t N1 | mémoire à 5 min | mémoire à 10 min | budget, 110 M nœuds |
| sk48 N2 | mémoire à 19 min | mémoire à 6 h 13 | budget, 48 M |
| sp80 N4 | mémoire à 15 min | mémoire à 56 min | budget, 120 M |
| tr87 N6 | mémoire à 3 min | mémoire à 8 min | budget, 31 M |
| m0r0 N6 | budget, 133 M nœuds (8 h 20) | budget | budget, 53 M |
| ka59 N4 | — | — | budget, 261 M |
| re86 N5 | — | — | budget, 19 M |
| sc25 N5 | — | — | budget, 40 M |
| su15 N4 | — | — | budget, 26 M |
| lf52 N3 | — | — | **espace épuisé sans issue**, 33 M nœuds (7 h 07) |
| bp35 N2 | — | — | budget, 12 M |
(— : bras non lancé sur ce niveau ; les 7 derniers niveaux n'ont que le bras `profondeur`, CW-307.) Tout plan est rejoué dans le vrai jeu.
Contrôle de `profondeur` à 300 s sur les 27 niveaux P0 gagnés par la référence : 14/27, 0 plan faux (`budget100_pod/controle/`).

## 3. Lecture
- **Aucun niveau classé S ne tombe à ×100**, ni par la mémoire (meilleur d'abord), ni par le temps (`profondeur`, jusqu'à 2,6 × 10⁸ nœuds).
  Les deux victoires (dc22 N4, ls20 N4) sont des niveaux M, déjà gagnés à règles exactes en 300 s.
- **Le meilleur d'abord bute sur la mémoire en 3 à 19 min** (prédiction confirmée) ; m0r0 N6 seul tient 8 h 20 (1,3 × 10⁸ nœuds) sans plan.
- **Contraste décisif** : g50t N1, 110 M nœuds sans plan en 8 h 20, est gagné **en 0,1 s** par les macro-actions de G (CCM-017-G).
  Le verrou des S est l'**horizon et le guidage**, pas la vitesse ni la mémoire. Conforme à la charte (solveur spécialisé).
- **lf52 N3 : espace épuisé sans issue** (approfondissement complet jusqu'à la profondeur limite, table par empreinte). Soit le plan dépasse
  4 096 coups, soit le **programme exact ne permet pas de gagner** ce niveau (règles incomplètes) : à vérifier par B (vérités corrigées).

## 4. Coût
CPU seul : 18 + 7 processus, ≈ 8 h 20 chacun (≈ 200 h CPU), sur un pod déjà payé pour le GPU. Mémoire de pointe ≤ 8 Go par processus (garde).

## 5. Niveau de revendication
B pour « ×100 de temps ne gagne aucun S à règles exactes avec ces recherches » (13 niveaux, 1 tirage déterministe). Aucun pour un niveau
au-delà de 4 096 coups.

## 6. Échecs d'exécution
Aucun plantage. Arrêts « mémoire » = raison d'arrêt prévue, pas des échecs. Programmes antérieurs à la correction du budget (`66caae4`).

## 7. Incertitudes
Empreinte 64 bits dans `profondeur` (collision possible, probabilité ≈ 10⁻³ à 2,6 × 10⁸ états) ; limite de profondeur 4 096 ;
budgets de coups absents des programmes au moment du test.
