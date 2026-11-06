# Mesure quotidienne des 13 niveaux frontière — 21/10, 5 h (CW-294.6, CW-315), A

Copie figée `44a80e0d` : programmes **corrigés par B** (su15 : avant son correctif « clic sur le plateau » de CCM-237-B) (budget de coups et défaite, `66caae4`, ar25 et su15 `97f20c7`), G allumé, COPIE
allumé. Plafond exact = sous-buts du défi 6, puis `langage_but` (recherche du moteur, CCM-014-G), puis `but` et `paliers` de `plafonds`,
300 s et 200 000 nœuds chacun ; tout plan rejoué dans le vrai jeu. Moteur réel : historique de Franzen observé puis moteur seul 10 min
(PARTIEL=2, AMODAL, BUT_SUPPOSE). Entonnoir (CW-315) : dernier maillon atteint par le moteur réel. Sorties : `frontieres_21-10/`.

| niveau | classe | plafond exact (recherche, coups) | moteur réel : dernier maillon |
|---|---|---|---|
| dc22 N4 | M | `langage_but`, 65 | 6 plan exécuté (sans victoire) |
| ka59 N4 | M | sous-buts, 60 | 1 perçus |
| ls20 N4 | M | **`langage_but`, 43** (hier : `paliers`, 44) | 1 perçus |
| re86 N5 | M | `langage_but`, 82 | 1 perçus |
| g50t N1 | S | aucun (budget) | 1 perçus |
| lf52 N3 | S | aucun (palier introuvable) | 1 perçus |
| m0r0 N6 | S | aucun | 1 perçus |
| sc25 N5 | S | aucun | 1 perçus |
| sk48 N2 | S | aucun | 1 perçus |
| sp80 N4 | S | aucun | 6 plan exécuté (sans victoire) |
| su15 N4 | S | aucun | 1 perçus |
| tr87 N6 | S | aucun | 1 perçus |
| bp35 N2 | — | **pas de résultat** : arrêté par le délai de 1 h, journal vide (comme hier et chez B : préfixe long à rejouer) | |

- **À règles corrigées, rien n'est perdu** : les 4 niveaux M gardent un plan exact, même longueur (dc22, re86, ka59) ou plus court (ls20).
  Aucun plan refusé pour dépassement du budget du niveau.
- **Moteur réel : 0 victoire sur 12.** 10 niveaux s'arrêtent au maillon 1 (« perçus » : appels du moteur, porte 1 jamais passée → la théorie
  ne rejoue pas, CCM-224-B) ; dc22 N4 et sp80 N4 vont jusqu'au plan exécuté, démenti par le vrai jeu.
- **Hors banc, la nuit** : g50t N1 gagné à règles exactes par les macros de G (0,1 s, CCM-017-G), et la théorie induite de C rejoue 129/129
  transitions de Franzen sur g50t N1 (CCM-195-C) : g50t N1 est le candidat le plus proche d'une victoire « depuis les observations ».
