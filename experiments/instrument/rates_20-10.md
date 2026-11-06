# Banc des niveaux frontière ratés par Franzen (CW-260/278) — 20/10, pod, copie figée `af7a158`

Préfixes : coups de Franzen R0 jusqu'au niveau frontière (`prefixes_r0.json`, vérifiés en jeu, si présents ; sinon `plafonds.prefixe`, vérifiés en
CCM-253-A). Plafond exact = règles et but exacts : sous-buts du défi 6 (300 s, 200 000 nœuds), puis `but`, puis `paliers` ; plan rejoué dans le
vrai jeu. Moteur réel = historique Franzen observé, puis moteur seul 10 min (`PARTIEL=2`, `AMODAL`, `BUT_SUPPOSE` + défauts).

| niveau | Franzen R0 | plafond exact | par | coups du plan | moteur réel | classe |
| --- | --- | --- | --- | --- | --- | --- |
| dc22 N4 | 3/6 | **atteint** | but | 65 | 0 | **M** |
| ka59 N4 | 3/7 | **atteint** | sous-buts (défi 6) | 60 | 0 | **M** |
| ls20 N4 | 3/7 | **atteint** | paliers | 44 | 0 | **M** |
| re86 N5 | 4/8 | **atteint** | but | 82 | 0 | **M** |
| g50t N1 | 0/7 | non | — | — | 0 | S |
| lf52 N3 | 2/10 | non | — | — | 0 | S |
| m0r0 N6 | 5/6 | non | — | — | 0 | S |
| sc25 N5 | 4/6 | non | — | — | 0 | S |
| sk48 N2 | 1/8 | non | — | — | 0 | S |
| sp80 N4 | 3/6 | non | — | — | 0 | S |
| su15 N4 | 3/9 | non | — | — | 0 | S |
| tr87 N6 | 5/6 | non | — | — | 0 | S |
| bp35 N2 | 1/9 | en cours | | | | |

- **4 niveaux sur 12 ont un plan à règles exactes** : c'est la liste de travail « règles » (M) pour C et D. Le moteur réel n'en gagne aucun.
- **8 niveaux S** (aucun plan en 300 s par stratégie, même à règles exactes) : liste pour le défi 6 final, F et E (CW-265, CW-273).
- Le plafond « but » de dc22 N4 (65 coups) est la référence que le défi 6 citait ; les sous-buts seuls ne le trouvent pas en 300 s.
