# Diagnostic à 4 configurations (CW-224.1) — 19/10 nuit, Mac, sélection figée (SELECTION.md), K = 40, graine 0

Rappel des configurations : **A** = règles induites + but inféré ; **B** = induites + but exact (but induit par C avec la démonstration gagnante de D) ;
**C** = exactes (vrai jeu copié) + but inféré ; **D** = exactes + but exact (P0). Données : `diag4_k40_g0.json`.

| jeu | amorce rejouée (recalé) | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| ft09 | 40/40 | aucun but planifiable | but **inexprimable** | aucun candidat atteint (budget) | **gagné** (4 coups) |
| tn36 | 36/40 | aucun but planifiable | but **inexprimable** | aucun candidat | **gagné** (7) |
| re86 | **0/40** | but supposé `remplir`, diverge au **1ᵉʳ coup** | but **inexprimable** | aucun candidat atteint | **gagné** (21) |
| sp80 | 20/29 | `remplir` supposé, 3/4 coups prédits justes, diverge au 1ᵉʳ | but **inexprimable** | vraie victoire *rencontrée* en cherchant `remplir` (*) | **gagné** (5) |
| ls20 | 39/40 | `sortie` supposé, 5/6 justes, diverge au 1ᵉʳ | but induit `ancre`, 5/7 justes, diverge au 1ᵉʳ | vraie victoire *rencontrée* (*) | **gagné** (13) |
| tr87 | **0/40** | `sortie` supposé, 0/12 justes | but **inexprimable** | aucun candidat atteint | **gagné** (16) |

(*) La recherche en largeur dans le vrai jeu a croisé la vraie victoire AVANT d'atteindre le but supposé. Ce n'est **pas** une preuve que
le but inféré est juste : ces deux « gagné » comptent comme une recherche exacte qui tombe sur la victoire.

## Lecture (quel maillon bloque, par niveau)
1. **D gagne 6/6** : l'outil et les règles exactes sont sains (contrôle).
2. **But** : maillon cassé sur **6/6**.
   - Le but exact n'est **pas exprimable** dans le vocabulaire de buts de C sur 5/6, même quand on montre la démonstration gagnante (B).
   - Sur ls20, il l'est (`ancre`), mais sans plan juste.
   - Aucun but supposé n'est atteint avant la vraie victoire (C).
3. **Règles** : maillon cassé sur au moins **4/6**.
   - re86 et tr87 : la théorie ne rejoue même pas l'amorce (0/40).
   - Partout où A ou B jouent, la 1ʳᵉ prédiction du plan est fausse. **À contrôler** : la divergence au 1ᵉʳ coup après RESET est systématique (4 sur 4) ; il peut s'agir d'un artefact de l'image initiale.
4. **Ordre des chantiers que cela donne** : (i) vocabulaire de buts de C, puisque B est inexprimable sur 5/6 ; (ii) règles sur re86 et tr87 ; (iii) vérifier l'artefact du 1ᵉʳ coup.

Échecs d'exécution : 2 boucles sans fin dans l'outil (amorce de sp80, budget des buts supposés), corrigées puis relancées ; 0 plantage dans les résultats.
