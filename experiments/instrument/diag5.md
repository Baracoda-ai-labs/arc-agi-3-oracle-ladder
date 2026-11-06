# Diagnostic à 5 configurations (CW-230) — 19/10 soir, Mac, sélection figée, K = 40, graine 0, HEAD de C (but `motif_rel`)

Lettres de CW-230. A = objets exacts + dynamique exacte + but exact ; B = état PERÇU + dynamique exacte + but exact ;
C = objets exacts + dynamique induite + but exact (**pas encore mesuré**) ; D = perçu + induite + but exact ; E = perçu + induite + but inféré.
Données : `diag5_k40_g0.json` (champs : A→`D`, B→`Bp`, D→`B`, E→`A` ; `C` = ancienne config « exacte + but inféré », gardée pour mémoire).

| jeu | A | B (perception, sur le chemin gagnant de A) | D | E | (ancienne : exacte + but inféré) |
| --- | --- | --- | --- | --- | --- |
| ft09 | **gagné** | faute à t=0, identité (sprite `cgN`) | **gagné** (`motif_rel`) | **gagné** (`motif_rel` supposé) | aucun candidat atteint |
| tn36 | **gagné** | faute à t=0, identité (`buojsacorqds`) | but inexprimable | aucun but planifiable | aucun candidat |
| re86 | **gagné** | faute à **t=7**, **position** (`0030rxzjuipynt`, objet 11 1×3) | but inexprimable | `remplir` supposé, diverge au 1ᵉʳ coup | aucun candidat atteint |
| sp80 | **gagné** | **juste sur tout le chemin (5 coups)** | but inexprimable | `remplir` supposé, diverge au 1ᵉʳ coup | victoire croisée |
| ls20 | **gagné** | faute à t=0, identité (`eqatonpohu`) | `ancre` induit, plan faux | `sortie` supposé, diverge au 1ᵉʳ coup | victoire croisée |
| tr87 | **gagné** | faute à t=0, identité (sprite `background`) | but inexprimable | aucun but planifiable | aucun candidat atteint |
| **total** | **6** | **1** | **1** | **1** | — |

## Lecture
1. **E (le système réel) : 1/6, contre 0/6 la nuit précédente.** C'est ft09, par le but `motif_rel` de C. D gagne aussi ft09. Le but reste le maillon cassé sur les 5 autres (inexprimable sur 4, faux sur ls20).
2. **B mesure l'EXACTITUDE de la perception, pas sa SUFFISANCE** (Cowork, CW-231). Il échoue sur ft09 alors que D et E y gagnent.
   - 4 des 5 fautes sont à t=0 et touchent des **sprites de décor** (fond, cadres, panneaux) : vus seuls, leurs pixels visibles ne forment pas les composantes que la perception tire de l'image entière.
   - C'est un **problème d'interface** entre sprites du moteur et objets de C (CW-230.1), pas forcément une erreur utile au plan. **À affiner** : juger seulement les sprites mobiles ou ceux que lit la victoire.
   - **Seule vraie faute de position : re86 à t=7**, cohérente avec CCM-102-C (la perception casse la sélection).
3. **C de CW-230** (objets exacts + dynamique induite) : demain matin. Il faut donner à l'induction des objets construits depuis les sprites.

Échecs d'exécution : configuration B absente du 1ᵉʳ passage (fonction placée après le point d'entrée du script) ; corrigée et recalculée à part. Aucun autre.
