# Pré-enregistrement GEL27 — moteur seul, code figé, un passage sur les 5 témoins (CW-412.5, CW-429)
Date de commit : brouillon 23/10 0 h 30 (`c7efac1d`) ; **FINAL 23/10 ≈ 1 h 30 (H)**, après livraison du paquet de C
(CCM-311-C) | Jeux : vc33, tu93, wa30, s5i5, cn04 — **aucun fichier de ces jeux n'a été ouvert par H** | Graine : 0, un passage.
Statut : **FINAL**, amendé le 23/10 au soir pour le paquet v3 (encadré ci-dessous), avant tout passage. Du brouillon au final n'ont changé que le paquet, l'empreinte, l'ordre et les contrôles (ceux de C,
CCM-310/311-C) ; p_dev inchangé (aucune nouvelle mesure « tenue à l'écart »). Règles, métrique, prédiction, critère : identiques.

**Provenance (ajout du 23/10, CW-445, avant tout passage ; rien d'autre ne change)** : réserve de `docs/TEMOINS.md` — le
catalogue T2.8 de B a lu les 25 sources, ces 5 compris, avant la règle d'exclusion ; des recherches extérieures (ChatGPT) ont
croisé des informations sur **cn04**, **non transmises aux agents**. Un résultat sur cn04 sera rapporté avec cette réserve.

**AMENDEMENT 23/10 19 h 45 (CW-461, décision de Thomas, AVANT tout passage)** — le paquet du 27 devient le **v3**.
- **Paquet** : `experiments/GEL27_moteur_seul_v3/` (commit `66614b3a`, **empreinte `fc9d27a3ee4168f437ccd8aa5d3772ef08c740a07544240bebc23c51f61e58e7`**,
  159 fichiers) = P1 + films F1 + nouveauté de G + bande3 + correctif bilan + **T1b : MoteurC joue dans P1** (`CHRYS_P1_MOTEUR=joue`,
  `CHRYS_BUT_SUPPOSE=1`, `CHRYS_P1_MOTEUR_CPU=30`, posés par `lancer.sh`). **Provisoire jusqu'à la bascule de C samedi soir** :
  si `CHRYS_BUTS_MAX=0` (D) ou l'objet contrôlé (E) entrent par mesure combinée avant samedi 16 h, l'empreinte change ; H recopie
  ici l'empreinte finale donnée par C au canal, et rien d'autre.
- **Commande** : `GEL27_TEMOINS=1 experiments/GEL27_moteur_seul_v3/lancer.sh <DOSSIER_TEMOINS> <SORTIE>`.
- **Contrôles bloquants (remplacent le § 7 pour v3)** : `GEL27_moteur_seul_v3/verifier.sh` → « paquet conforme » à l'empreinte
  finale ; rejeu au coup près **ar25 37 / 23 / N3 perdu** (v1 : 39/27, la nouveauté de G change ar25) et **ka59 11, 50, 35, 46, 39,
  N6 perdu** ; le `meta` des journaux porte `paquet.conforme = true` et les 6 drapeaux.
- **Mesures de développement de v3** (pour information ; elles n'entrent pas dans p_dev) : 20 publics, graines 0/1 : v2 19/19 →
  v3 22/20 (ft09, jeu de développement = contrôle positif) ; T4 (104 jeux générés), graines 0/1 : 101/102 → 104/108, dont
  4 niveaux gagnés par MoteurC que P1 seul perd, 2 perdus (effets de trajectoire) (CCM-333/334-C, CCM-310/313-B).
- **Deux révisions faites APRÈS avoir vu des résultats, déclarées** : (1) la **porte de T1** (une « interaction » = action +
  couleur visée au lieu du pixel exact), corrigée après le refus de ft09 au 1ᵉʳ passage (CCM-333-C) ; (2) la **règle
  d'imputation des pertes** de B (imputable si MoteurC intervient avant le coup où la référence gagnait), affinée après le bras
  marge (CCM-313-B). Le critère d'entrée de CW-456 (0 perdu sur T4) n'était pas tenu ; celui de CW-458 (0 perte imputable)
  l'est avec la règle affinée. Ni l'une ni l'autre ne touche un témoin.
- **Prédiction : inchangée, par la règle figée du § 5** (p_dev = jeux ARC tenus à l'écart du développement, code figé, un
  passage ; aucune mesure de ce type ajoutée ; les 20 publics et T4 sont du développement) → **k̂ = 0,39, 0 témoin prédit**.
- **Ce que le passage mesure désormais** : un niveau de témoin attribué `moteur` (plan de MoteurC) soutiendrait l'ontologie,
  l'induction et le solveur ensemble ; un niveau attribué à l'exploration ou à la boucle de familles soutiendrait l'agent
  seulement. **Mesure secondaire ajoutée** : attribution de chaque niveau gagné (moteur / exploration / famille) et entonnoir
  compté de MoteurC par témoin (occasions → … → interventions → résultat), lus dans les journaux.

**RÈGLE D'IMPUTATION, figée le 23/10 à 23 h 55 (CW-467.2), applicable de manière prospective au seul passage du 27** :
une perte de niveau sur un témoin est **imputable à MoteurC** si MoteurC est intervenu sur ce niveau ; à défaut de
référence sur les témoins (aucun passage de référence n'y est joué), **toute perte sur un niveau où MoteurC est intervenu est
rapportée comme imputable**, et toute perte sans intervention comme indirecte. Cette règle dérive de celle de B (CCM-313-B :
« avant le coup où la référence gagnait »), affinée **après** les résultats de T1 sur T4 ; elle est figée ici avant le passage
et n'est plus modifiée. Elle sert à l'attribution (mesure secondaire), pas à la métrique principale.

**PRÉCISIONS 24/10 (CW-483, avant tout passage ; prédiction et métriques inchangées)** :
- **Périmètre** : le test porte sur les **5 témoins seulement** ; les 20 publics sont du développement et les 104 jeux T4 sont générés (pas ARC). Le résultat est rapporté comme limité, jeu par jeu.
- **Attribution FIGÉE = règle de B (`cf2a1f81`), sans nouvel ajustement** ; on publie d'abord le **gain total apparié** (là où une référence existe ; sur les témoins, sans passage de référence, c'est la métrique principale du § 3), puis l'attribution au moteur comme explication.

## 1. Hypothèse principale (une phrase)
Le moteur seul (sans LLM), réglé uniquement sur les 20 jeux publics non témoins, **gagne au moins un niveau d'un jeu ARC
jamais vu** en partant de RESET.

## 2. Ce qui est joué (liste fermée)
| élément | valeur |
|---|---|
| candidat | paquet de C `experiments/GEL27_moteur_seul/` : agent P1 (v4 + inventeur) + **exploration générique d'origine** (OW présent, non utilisé : moins bon sur 3 graines des 20 publics, CCM-311-C) ; aucun LLM, aucune variable `CHRYS_*` |
| code | commit `81126387` ; **empreinte globale `a6f847dafa143cc100b64ff1dc4482862faa66b0e2b744f1e3ce2a132520a98b`** (sha256 de `SHA256SUMS`, 59 fichiers, `EMPREINTE.txt`) ; le lanceur la revérifie (code 4 = refus) |
| commande | `GEL27_TEMOINS=1 experiments/GEL27_moteur_seul/lancer.sh <DOSSIER_TEMOINS> <SORTIE>` (`PROTOCOLE.md` du paquet) |
| départ | RESET de chaque témoin, niveaux enchaînés ; **150 coups par niveau**, RESET compris ; arrêt du jeu au premier niveau perdu ; mémoire inter-jeux de départ copiée, l'original intact |
| arrêt dur | celui du lanceur de C ; échec d'exécution = 0 niveau, **compté** |
| ordre | alphabétique (cn04, s5i5, tu93, vc33, wa30), comme en développement ; un passage ; **aucune retouche entre jeux, aucune relance** |
| interdit | lire un fichier d'un témoin avant le passage ; afficher l'image ou le code d'un témoin pendant ; tout LLM |
| journal | une ligne par niveau : jeu, niveau, gagné, coups, cause d'arrêt ; rien d'autre n'est lu avant le rapport |

## 3. Métriques (population entière, échecs comptés, Wilson 95 %)
- **Principale** : nombre de témoins dont **au moins un niveau** est gagné (sur 5).
- Secondaires : niveaux gagnés au total ; coups par niveau gagné ; part des jeux arrêtés par temps ou mémoire ; score
  ARC estimé si l'arcade le rend (sinon non rapporté). Aucune médiane sur les seuls gagnants sans le nombre d'échecs.

## 4. Taille (déclarée)
n = 5 jeux, une graine. Seule issue informative : **≥ 1 témoin gagné** (Wilson pour 1/5 : [0,04 ; 0,62]). 0/5 est
compatible avec tout taux ≤ 40 % : on l'écrit « non concluant, pas de généralisation démontrée », jamais « 0 % ».

## 5. Prédictions chiffrées
**Règle fixée maintenant** (même règle que le pré-enregistrement des témoins du 20/10) : k̂ = 5 × p_dev × 0,78, où
- p_dev = part des jeux **tenus à l'écart du développement** (codes figés, un passage) dont au moins un niveau est gagné,
  toutes mesures de C ou G de ce type datées avant le FINAL, poolées ; 0,78 = décote public → caché de Franzen (CW-103).
- **Valeur au brouillon** : CW-409, deux lots de 5 (0/5 puis 1/5, tn36 N1) → p_dev = 1/10 = 0,10 → **k̂ = 0,39**.
- Au FINAL : aucune mesure du même type ajoutée (C : les 20 publics sont du développement) → **p_dev = 0,10, k̂ = 0,39**.
- Pour information, non utilisé : en développement (20 publics, depuis RESET, 2 graines) ce paquet gagne ≥ 1 niveau sur
  **7/20** jeux (18 niveaux, score 16,9). La même règle appliquée à ce taux donnerait k̂ = 1,37 ; l'écart entre 0,10 et
  0,35 est précisément ce que le passage mesure.

| mesure | développement | prédiction témoins | issue qui la contredirait |
|---|---|---|---|
| témoins avec ≥ 1 niveau gagné (sur 5) | p_dev = 0,10 | **0** (k̂ = 0,39 < 0,5) | ≥ 2 |
| niveaux gagnés au total | tenus à l'écart : 1 sur 10 jeux | **0 ou 1** | ≥ 3 |
| coups par niveau gagné | tn36 N1 : 38 (OW) | ≤ 150 (budget) | — |
| jeux arrêtés par temps ou mémoire | à lire dans le rapport de C | ≤ 2/5 | ≥ 4/5 (le passage ne mesure alors que l'infrastructure) |

## 6. Critère (CW-412.5, décision de Thomas)
**≥ 1 niveau gagné sur un témoin** → la section « généralisation » de l'article peut être écrite, niveau de revendication
au plus C (n = 5). **0** → pas d'article sur la généralisation ; on écrit le rapport honnête. Pas de second passage, pas
d'autre graine pour « rattraper ».

## 7. Contrôles avant le passage (bloquants)
1. `experiments/GEL27_moteur_seul/verifier.sh` → « paquet conforme : global a6f847da…20a98b ».
2. **Rejeu au coup près** (tient lieu de F-C2 : le paquet ne lit aucun drapeau à éteindre) : ar25 → N1 39, N2 27, N3 perdu ;
   ka59 → N1–N5 en 11, 50, 35, 46, 39, N6 perdu. Tout écart → STOP, pas de passage.
3. `GEL27_TEMOINS=1` posé **seulement** dans la commande du passage ; sans lui le lanceur refuse les témoins (code 3).
4. Session qui lance : désignée par Cowork (pas C) ; elle n'ouvre aucun fichier des témoins hors du lanceur.

## 8. Ce qui n'est PAS testé ici
Le score Kaggle (Franzen + moteur) ; l'ensemble verrouillé T4 (20 jeux à paires inédites, `experiments/verrou/SCELLE.md`) et
le lot à l'écart : ils ont leurs propres mesures, jamais fusionnées avec celle-ci ; tout réglage fait après avoir vu un
témoin (il n'y en aura pas).
