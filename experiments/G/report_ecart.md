# Preuve A, cas tenu à l'écart (CW-337.1) — rapport court standard (21/10, 10 h 30)
**Version** : `macro_moteur.py` gelé au commit `00d489bb` (algorithme de `macro_g` `f9fb62a4`, simulateur = vrai moteur ;
3 écarts déclarés en CCM-025-G) ; banc `banc_ecart.py` (même commit) ; lot à l'écart de H (w000, w001, empreinte
`ddbc0725…`), ouvert sous `CHRYS_ECART=1` et garde de B, **une seule passe**.
**Changement mesuré** : macros sur l'objet piloté (`macro_moteur`) contre la recherche de référence (largeur dans le
vrai moteur, `resoudre_niveau`), 300 s CPU chacune par niveau ; les deux sont exactes (le moteur simule).

| jeu (mécaniques) | niveau | optimum | référence | macro |
|---|---|---|---|---|
| w000 (glace, pousser, cibles, trous) | 1 | 11 | gagné 11 (0,2 s) | gagné 11 (0,0 s) |
| | 2 | 11 | gagné 11 (0,1 s) | gagné 11 (0,0 s) |
| | 3 | 12 | gagné 12 (0,2 s) | gagné 12 (0,1 s) |
| | 4 | 18 | gagné 18 (2,3 s) | gagné 18 (108 s) |
| | 5 | 27 | gagné 27 (17,5 s) | **échec** (budget 300 s) |
| w001 (portail, poursuivant, pousser) | 1 | 15 | gagné 15 (0,2 s) | gagné 15 (0,1 s) |
| | 2 | 16 | gagné 16 (1,7 s) | gagné 16 (0,1 s) |
| | 3 | 16 | gagné 16 (1,7 s) | gagné 16 (0,2 s) |
| | 4 | 15 | gagné 15 (3,2 s) | gagné 16 (0,4 s) |

**Résultat** : référence 9/9 [Wilson 95 % : 70–100 %], macro 8/9 [57–98 %] ; **gagnés par la macro seule : 0** ;
par la référence seule : 1 (w000 N5). Plans de la macro optimaux sauf w001 N4 (16 contre 15).
**Lecture** : sur ce lot, les niveaux sont courts (11–27 coups) et la largeur dans le vrai moteur les résout tous en
≤ 17,5 s. La macro est plus rapide sur 6 niveaux, plus lente sur w000 N4, et perd w000 N5 (pousser sur glace : il faut
revenir sur une case après qu'une caisse a glissé, ce que la nouveauté sur la seule position du joueur coupe).
**Preuve A** : l'avantage mesuré sur les jeux publics (4 niveaux gagnés par la seule macro, CCM-022-G et banc apparié
`97f20c73`) **ne se reproduit pas** sur le cas tenu à l'écart : **aucun niveau gagné en plus**. Niveau de revendication
de la preuve A : partielle, 2 mécanismes publics, **sans confirmation à l'écart**.
**Régressions** : aucune (rien n'est allumé ni branché par ce banc).
**Prochaine décision** (Cowork) : (a) en rester là pour la preuve A ; (b) un lot à l'écart plus dur (niveaux où la
largeur échoue à 300 s), seul cas où un avantage peut se montrer ; (c) corriger la perte de w000 N5 (nouveauté
(position du joueur, positions des objets poussables)), puis nouvelle passe sur un AUTRE lot, celui-ci étant consommé.
