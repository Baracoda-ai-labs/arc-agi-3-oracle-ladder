# Pourquoi P1 perd le niveau suivant (F, CW-449) — 23/10, 13 h 30, Mac

**Situation.** On donne à P1 le plan exact du niveau qu'il perd. Il le gagne (11 sur 11), puis il **perd seul le niveau suivant dans les 11 jeux** (CCM-047-F, `p1_oracle_plan.py`, contrôle 18 = 18).

## Ce que P1 fait sur ces 11 niveaux suivants (`p1_oracle_resume.json`, journaux de niveau)
| niveau suivant | agent v4 | exploration générique | morts | P0 (tout exact, pod) |
|---|---|---|---|---|
| cd82 N2, tr87 N2 | lancé, « v4 seule » sans victoire | 150 coups épuisés | 1 | **gagne** |
| dc22, ls20, re86, sp80 N2 ; m0r0 N3 | **« non reconnu »** (scène inconnue) | 150 coups épuisés | 0 à 7 | gagne (dc22, ls20, re86, sp80) ; budget (m0r0 N3) |
| ft09, su15 N2 ; lp85 N3 | pas lancé (pas de flèches) | 150 coups épuisés | 1 à 2 | gagne (ft09) ; budget (su15, lp85 N3) |
| lf52 N2 | « non reconnu » | 150 coups épuisés | 0 | budget |

**Constat.**
- Sur ces 11 niveaux suivants, P1 est **dans la même situation qu'au premier niveau** de ces jeux : la v4 ne reconnaît pas la scène, et l'exploration générique épuise ses 150 coups.
- **P1 ne perd rien entre deux niveaux : il n'avait rien appris.** Le plan oracle est joué, pas appris.
- Même motif **sans oracle** : les 4 jeux où P1 gagne un N1 par l'exploration générique (lp85, m0r0, r11l, tn36) perdent tous le N2 (`dev/generique`).

## Ce que P1 garde d'un niveau à l'autre (code figé, `agent_p1/jouer.py`, `generique.py`, `labo.py`)
**Gardé :**
- l'environnement ;
- la mémoire de coups (`Memoire` : taux d'effet et de victoire par **type d'action**, par jeu et entre jeux) ;
- la bibliothèque de l'inventeur.

**Refait à zéro à chaque niveau :**
- l'agent v4 (perception, hypothèses) ;
- le graphe d'exploration (clé = image) ;
- l'évaluateur de progrès.

**Jamais gardé :**
- l'objet contrôlé ;
- la forme du but ;
- les règles ;
- le chemin gagnant.

## Deux correctifs bon marché, mesurés : 0 sur 11
1. **Rejouer tel quel le plan gagnant du niveau précédent** au début du niveau suivant (`rejeu_suivant.py`, hors ligne, préfixes R0) : **0 / 11**. Les positions changent d'un niveau à l'autre.
2. **Nourrir la mémoire de coups avec les coups du plan gagnant**, comme pour une victoire de l'exploration générique (`p1_oracle_plan.py --transfert`).
   - La mémoire change bien (exemple cd82 : `k5` porte une victoire) et le comportement aussi.
   - Mais **0 niveau suivant gagné** : 29 = 29.
- **Critère** « +1 niveau suivant, 0 perdu » : **non atteint** par les deux.

## Lecture
- Les niveaux suivants sont **solubles avec les connaissances exactes** : P0 en gagne **7 sur 11**.
- Ce qui manque à P1 pour enchaîner, ce n'est pas un report de mémoire, c'est **une connaissance transférable du jeu** : l'objet contrôlé, la forme du but, une loi.
- C'est le verrou du chantier commun **« objet contrôlé »** (CW-449 : D pilote, E, C) : la v4 ne reconnaît pas la scène dans 6 de ces 11 niveaux, et la théorie induite n'a pas d'objet contrôlé dans 5 cas sur 6 (CCM-088-D).

## Proposition
F mesure la valeur de ce maillon **dans P1** par un oracle d'**objet contrôlé exact** : le sprite du joueur, lu dans le moteur du jeu par le banc, injecté là où la v4 et l'exploration le cherchent.
- Bras : N1 des 13 jeux perdus, et niveau suivant des 11 jeux ci-dessus.
- **Critère** : au moins +1 niveau, 0 perdu.
- S'il est positif, il borne ce que le chantier de D peut rapporter. S'il est nul, le chantier doit viser le but avant le contrôlé.

**Limites.**
- Une seule graine.
- Les plans P0 ne sont pas minimaux.
- m0r0 N3, lp85 N3, su15 N2 et lf52 N2 sont hors de portée de P0 au budget du pod.
