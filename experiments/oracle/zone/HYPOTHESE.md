# CHRYS_F_ZONE — hypothèse écrite AVANT toute mesure (F, CW-468.2, CW-473.2), 24/10, 1 h 40

**Origine (développement)** : autopsie des interventions de T1 sur T4 graine 0 (`experiments/oracle/autopsie/`).
- 36 échecs : **21** où le plan fait sortir l'objet contrôlé du terrain, par un bord ou un panneau jamais heurté (le vrai jeu bloque, la théorie non) ; 10 buts faux ; 4 blocages dans le terrain ; 1 autre.
- Hors ligne, le filtre « zone observée » signale 15 des 21 échecs « hors terrain » et 0 des 8 victoires.

**Correction (générique, sans vérité T4 ni oracle)** : `CHRYS_F_ZONE=1`. Dans le planificateur, une position où un objet dynamique sort de la boîte des cases où un changement a déjà été vu dans le niveau est traitée comme bloquée. Jeux à clic : sans effet. Éteint : code identique (test `tests/test_zone_plan.py`). SHA au commit de ce fichier.

**Hypothèse** : en replanifiant dans la zone observée, le moteur évite des plans qui sortent du terrain. Il trouve soit un autre chemin vers le but (victoire possible), soit aucun plan (coups épargnés pour P1).

**Mesure** : lanceur T1 de C, `CHRYS_P1_MOTEUR=joue` + `CHRYS_F_ZONE=1`, contre T1b (`T1_releve_p1/runs/joue2_*`).
- **Développement** : T4 graine 0 (là où la cause a été trouvée).
- **Tenus à l'écart (jamais utilisés pour la trouver)** : **T4 graine 1**, **20 publics graine 0**, **20 publics graine 1**.

**Prédictions** :
- T4 g0 (dev) : divergences « hors terrain » 21 → **≤ 8** ; victoires du moteur 8 → **8 à 10** ; 0 niveau perdu.
- **Tenus à l'écart, critère** : **≥ +1 victoire attribuée au moteur sur T4 g1**, **0 niveau perdu** sur T4 g1 et sur les publics (g0 et g1). Publics : effet attendu ≈ 0, car peu de dédales à flèches.

**Arrêt** : 0 victoire en plus sur T4 g1, ou ≥ 1 niveau perdu imputable → pas de gel ; résultat rapporté tel quel.
