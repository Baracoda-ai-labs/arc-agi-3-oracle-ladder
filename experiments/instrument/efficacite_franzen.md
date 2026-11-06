# Efficacité de Franzen (CW-281) — coups de Franzen contre coups humains, et plans courts du moteur
(B : partie Franzen sur les 86 niveaux gagnés ; A : partie « plans à règles exactes » ci-dessous.)

## Partie A (CW-281) — plans à RÈGLES EXACTES contre humain et Franzen R0, par niveau
Sources des plans : P0 du pod (`but`, `paliers`, `compile`, 1 M nœuds / 600 s), défi 6 (5 plans vérifiés, CCM-260-A), défi 2 (13 plans
vérifiés par Cowork, CW-216), banc des frontières (CCM-260-A). Coups humains = `baseline_actions` (metadata.json). Coups Franzen R0 =
actions depuis la fin du niveau précédent, morts comprises (`franzen_R0_niveaux.json`). Score d'un niveau = min(1, h/a)², sans le poids du rang.
**Réserve majeure** : ce sont des plans à règles et but EXACTS (oracle de banc), pas des plans du moteur réel ; ils donnent la borne haute
de « Franzen découvre, le moteur exécute court ».

| jeu | niveau | humain | Franzen R0 | plan exact | source | score Franzen | score plan | gain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ar25 | N1 | 32 | 25 | 15 | défi 6 | 1 | 1 | +0 |
| ar25 | N2 | 50 | 16 | 16 | P0 paliers | 1 | 1 | +0 |
| bp35 | N1 | 21 | 23 | 44 | défi 2 | 0.83 | 0.23 | -0.61 |
| bp35 | N2 | 48 | — (raté) | 57 | défi 2 | 0.0 | 0.71 | +0.71 |
| bp35 | N3 | 44 | — (raté) | 87 | défi 2 | 0.0 | 0.26 | +0.26 |
| cd82 | N1 | 55 | 65 | 5 | P0 but | 0.72 | 1 | +0.28 |
| cd82 | N2 | 8 | 10 | 6 | P0 compile | 0.64 | 1 | +0.36 |
| cd82 | N3 | 41 | 42 | 24 | P0 paliers | 0.95 | 1 | +0.05 |
| dc22 | N1 | 59 | 48 | 20 | P0 but | 1 | 1 | +0 |
| dc22 | N2 | 102 | 88 | 42 | P0 but | 1 | 1 | +0 |
| dc22 | N4 | 98 | — (raté) | 65 | défi 6 | 0.0 | 1 | +1.0 |
| ft09 | N1 | 43 | 4 | 4 | P0 but | 1 | 1 | +0 |
| ft09 | N2 | 12 | 7 | 7 | P0 but | 1 | 1 | +0 |
| ft09 | N3 | 23 | 14 | 14 | P0 but | 1 | 1 | +0 |
| g50t | N1 | 78 | — (raté) | 49 | défi 2 | 0.0 | 1 | +1.0 |
| g50t | N2 | 175 | — (raté) | 41 | défi 2 | 0.0 | 1 | +1.0 |
| ka59 | N1 | 28 | 49 | 15 | P0 compile | 0.33 | 1 | +0.67 |
| ka59 | N3 | 51 | 81 | 35 | P0 but | 0.4 | 1 | +0.6 |
| ka59 | N4 | 51 | — (raté) | 60 | défi 6 | 0.0 | 0.72 | +0.72 |
| lf52 | N1 | 32 | 10 | 8 | P0 compile | 1 | 1 | +0 |
| lp85 | N1 | 17 | 7 | 5 | P0 but | 1 | 1 | +0 |
| lp85 | N2 | 38 | 11 | 10 | P0 but | 1 | 1 | +0 |
| ls20 | N1 | 22 | 29 | 13 | P0 but | 0.58 | 1 | +0.42 |
| ls20 | N2 | 123 | 130 | 45 | P0 but | 0.9 | 1 | +0.1 |
| ls20 | N3 | 73 | 139 | 39 | P0 but | 0.28 | 1 | +0.72 |
| ls20 | N4 | 84 | — (raté) | 44 | frontière paliers | 0.0 | 1 | +1.0 |
| m0r0 | N1 | 30 | 33 | 15 | P0 but | 0.83 | 1 | +0.17 |
| m0r0 | N2 | 111 | 76 | 23 | P0 but | 1 | 1 | +0 |
| r11l | N1 | 22 | 10 | 3 | P0 but | 1 | 1 | +0 |
| re86 | N1 | 26 | 21 | 21 | P0 but | 1 | 1 | +0 |
| re86 | N2 | 42 | 54 | 52 | P0 paliers | 0.6 | 0.65 | +0.05 |
| re86 | N3 | 86 | 47 | 59 | P0 but | 1 | 1 | +0 |
| re86 | N5 | 189 | — (raté) | 82 | frontière but | 0.0 | 1 | +1.0 |
| sb26 | N1 | 18 | 11 | 12 | défi 6 | 1 | 1 | +0 |
| sc25 | N2 | 6 | 6 | 5 | P0 but | 1 | 1 | +0 |
| sk48 | N1 | 61 | 45 | 15 | défi 6 | 1 | 1 | +0 |
| sk48 | N2 | 177 | — (raté) | 49 | défi 2 | 0.0 | 1 | +1.0 |
| sk48 | N3 | 101 | — (raté) | 40 | défi 2 | 0.0 | 1 | +1.0 |
| sk48 | N4 | 103 | — (raté) | 37 | défi 2 | 0.0 | 1 | +1.0 |
| sp80 | N1 | 39 | 11 | 4 | P0 compile | 1 | 1 | +0 |
| sp80 | N2 | 58 | 12 | 7 | P0 compile | 1 | 1 | +0 |
| su15 | N1 | 22 | 9 | 7 | P0 compile | 1 | 1 | +0 |
| tn36 | N1 | 32 | 21 | 7 | P0 but | 1 | 1 | +0 |
| tr87 | N1 | 54 | 31 | 16 | P0 but | 1 | 1 | +0 |
| tr87 | N2 | 58 | 33 | 21 | défi 2 | 1 | 1 | +0 |
| tr87 | N3 | 40 | 151 | 14 | défi 2 | 0.07 | 1 | +0.93 |
| tr87 | N4 | 45 | 32 | 24 | défi 2 | 1 | 1 | +0 |

- **Niveaux déjà gagnés par Franzen** (36 avec un plan exact) : gain cumulé **+3.74 niveau-équivalent** (non pondéré),
  concentré sur ls20 N1/N3, ka59 N1/N3, tr87 N3 (Franzen 151 coups contre 40 humains → score 0,07 ; plan exact 14 → 1,0), cd82 N1/N2 ;
  une perte : bp35 N1 (plan du défi 2 de 44 coups contre 23 pour Franzen).
- **Niveaux ratés par Franzen** (11 avec un plan exact) : gain cumulé **+9.69** — dont 4 frontières atteignables aujourd'hui
  (dc22 N4, ka59 N4, ls20 N4, re86 N5) ; les autres (g50t N1-2, bp35 N2-3, sk48 N2-4) supposent de gagner d'abord les niveaux d'avant.
- **Lecture** : à règles exactes, « le moteur exécute court » rapporterait ≈ +3,7 sur les niveaux déjà gagnés et ≈ +9,7 sur les niveaux ratés
  (dont seule une partie est atteignable aujourd'hui). Le verrou commun reste le même : le moteur RÉEL n'a pas les règles exactes (classe M). Avec le poids du rang (B), les niveaux
  tardifs (tr87 N3, ls20 N3) pèsent plus.

## Rectificatif (A, 21/10, CCM-289-A) : plafond par niveau = 1,15, pas 1
Le calculateur du harnais (`arc_agi` 0.9.9, `scorecard.py` l. 168-170) note un niveau `min(115, (h/a)² × 100)` : un plan plus court que
l'humain vaut jusqu'à 1,15. Recalculé avec min(1,15 ; (h/a)²) sur le même tableau :
- niveaux déjà gagnés par Franzen (36) : gain **+5,42** (au lieu de +3,74) ; Franzen lui-même profite aussi du plafond, quand il fait mieux que l'humain ;
- niveaux ratés par Franzen (11) : gain **+10,89** (au lieu de +9,69).
Les colonnes « score » du tableau restent celles de l'ancien calcul (plafond 1).
