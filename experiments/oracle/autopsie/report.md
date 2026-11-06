# Autopsie des interventions de MoteurC dans P1 (F, CW-467.3, 468, 470.2, 472.2, 473.2) — 24/10, nuit, Mac

## Deux chiffres en tête (CW-472.2)
- **(a) Échecs partageant une cause : 21 sur 36.** Dans T4 g0, mesure `BUTS_MAX=0`, la théorie fait **sortir l'objet du terrain**, par un bord ou un panneau jamais heurtés pendant la fenêtre, et le vrai jeu le bloque. Dans T1b, c'est 16 sur 28.
- **(b) Victoires réelles après correction : 0.**
  - La correction générique `CHRYS_F_ZONE` (figée `9d6dd5ea`) **échoue** sur les cas tenus à l'écart : T4 g1, **108 → 106 niveaux**, victoires du moteur **8 → 1**.
  - Elle n'entre pas au gel.

## Méthode (`autopsie.py`, `autopsie_classer.py`, sorties dans ce dossier)
- Chaque intervention journalisée (T1b `joue2_t4_g0` ; mesure de D `t1_tous_t4_g0`) est **reconstruite hors ligne** : fenêtre exacte de `releve_moteur.tenter` et `MoteurC.proposer` relancé. On ne joue aucun coup.
- On compare ensuite, coup après coup, le rendu prédit à l'image réelle (`partie.npz`), sur les **coups réellement exécutés**.
- **Fidélité** :
  - l'issue est reconstruite à l'identique dans **44/44** et **36/36** cas ;
  - le plan reconstruit est identique aux coups exécutés dans **44/44**.
  - Une première version comparait aussi les coups de P1 joués après l'intervention. Elle a été corrigée avant tout classement.
- **Classement à la 1ʳᵉ divergence** : on regarde d'abord si le coup a changé l'image réelle (≤ 8 px, la jauge seule, veut dire « bloqué »). La vérité de T4 (bordure, panneau) sert seulement à **nommer** ce qui bloque, jamais à corriger.

## Résultat : une ligne par famille (format de CW-468.1)

| 1ʳᵉ divergence | n (H4 / T1b) | cause | famille (CW-468) | colonne de CW-470 | contrôle préalable ? |
|---|---|---|---|---|---|
| déplacement prédit, réel immobile, cases **hors du terrain** | **21 / 16** | bord ou panneau jamais heurtés : la loi de blocage manque | loi insuffisante (interaction jamais observée) | modèle empirique | **en partie** : « quitte la zone des changements vus » signale 15/21, 0/8 victoires (hors ligne, sur tout l'historique du niveau) |
| objet déplacé, but supposé atteint, pas de victoire | 10 / 8 | but supposé faux (sortie ou ancre) | — (but) | modèle empirique | non (rien ne distingue le but avant d'essayer) |
| déplacement prédit, réel immobile, dans le terrain | 4 / 3 | obstacle intérieur jamais heurté | loi insuffisante | modèle empirique | incertain |
| changement réel non prédit | 1 / 1 | glace, interrupteur ou poursuivant (y000) | loi insuffisante | modèle empirique | non |
| **victoire** (contrôle positif) | 8 / 8 | plan prédit juste jusqu'au coup gagnant | — | — | — |

**Aucune** erreur de structure ni de conversion ou d'exécution (export, clic, coordonnées) n'est trouvée. Pour G (CW-470.3), cela veut dire **pas de chantier SKOS/SHACL** justifié par ces échecs.

## Correction essayée : `CHRYS_F_ZONE` (hypothèse et cas tenus à l'écart écrits AVANT, `../zone/HYPOTHESE.md`)
- **Règle** : dans le planificateur, une position où un objet dynamique sort de la boîte des cases où un changement a été vu est bloquée. Jeux à clic : sans effet. Éteint : identique (`tests/test_zone_plan.py`).

| banc (lanceur T1, joue) | T1b | + zone | moteur (victoires) | interventions |
|---|---|---|---|---|
| T4 g0 (développement) | 104 | 104 (+2 y014 et y018, −3 y026, y040, y049) | 8 → 1 | 36 → 5 |
| **T4 g1 (tenu à l'écart)** | **108** | **106** (−y026, −y042) | **8 → 1** | 37 → 6 |
| publics g0 / g1 (tenus à l'écart) | 22 / 20 | 22 / 20 | 3 / 1 → 3 / 1 | 4 → 3 ; 3 → 1 (divergences évitées, 0 perte) |

- **Verdict** : prédiction **fausse** ; critère **non atteint** (0 victoire en plus, 2 niveaux perdus sur T4 g1). **Arrêt, rien au gel.**
- **Pourquoi** :
  - le filtre vérifié hors ligne prenait la zone sur **tout l'historique du niveau** (pixels changés depuis son début) ;
  - le code la prend sur la **seule fenêtre de 40 coups** de la trajectoire, en cases. La zone est donc trop petite, et elle bloque aussi les plans gagnants : 36 interventions tombent à 5.
  - C'est une **erreur d'implémentation de F**, pas une réfutation de l'idée.
  - Corriger maintenant et remesurer sur T4 g1 serait du réglage sur résultat : **T4 g1 n'est plus tenu à l'écart**. Une version « historique du niveau » demandera un nouveau jeu de cas tenus à l'écart (après le gel).

## Incertitudes
- Une seule graine pour l'autopsie (T4 g0).
- La classe « bloqué » repose sur ≤ 8 px changés. Une jauge plus grande serait mal classée.
- Le contrôle préalable « 15/21, 0/8 » est un calcul rétrospectif : il désigne un candidat, il ne mesure pas un score (CW-469.6).
