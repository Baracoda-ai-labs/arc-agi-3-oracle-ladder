# Substitution d'oracle sur les niveaux perdus par P1 (F, CW-444 et CW-445) — 23/10, 10 h 30, Mac, HEAD `db030be4`

**1. Hypothèse et prédiction** (CCM-041-F, écrites avant la mesure)
- **Hypothèse** : le maillon le plus cher est le **but**, devant les règles.
- **Prédiction**, sur les 13 niveaux N1 : D 7 ± 1 ; C 3 ± 1 ; B 2 ± 1 ; A ≤ 1.
- **Contrôle positif** : D retrouve P0 du pod, à 2 écarts près au plus.

**Population.** Ce sont les **20 niveaux perdus par P1**, un par jeu (`GEL27_moteur_seul/dev/generique`). 18 sont mesurés. ka59 N6 et g50t N8 ne le sont pas : aucun préfixe enregistré n'atteint ces niveaux.

**Méthode.** P1 n'a ni étape « règles » ni but écrit dans notre langage. La substitution se fait donc sur la **chaîne du moteur** (`experiments/instrument/diag4.py`, inchangé), à partir du début du niveau perdu. Pour N > 1, `oracle_niveau.py` place le jeu au niveau k par le préfixe enregistré.
- **Amorce** : 40 coups au hasard (graine 0), les mêmes pour tous les bras.
- **La vérité reste chez l'évaluateur** : le vrai jeu ou le programme exact sert de simulateur et de juge, jamais de donnée pour l'agent.

**Les bras :**
- **A** : aucun oracle (règles induites, but inféré) ;
- **B** : but exact (le but que C induit en voyant la démonstration gagnante de D), règles et perception apprises ;
- **C** : perception et règles exactes (le vrai jeu sert de simulateur), but inféré. Lancé à 120 s, puis **à 600 s, le budget de D** (`bras_C_600.py`, CW-445) ;
- **D** : tout exact = P0 (recherche `but`, puis `paliers` ; 1 M nœuds / 600 s).

**2. Résultats** (18 niveaux ; détail niveau par niveau et causes CW-445 : `uv run python experiments/oracle/tableau.py`)

| bras | gagnés / 18 | Wilson 95 % |
|---|---|---|
| A aucun oracle | 1 (ft09 N1) | [1 %, 26 %] |
| B but exact, règles et perception apprises | 1 (ft09 N1) | [1 %, 26 %] |
| C règles et perception exactes, but inféré, 120 s | 3 (cd82, ls20, sp80) | [6 %, 39 %] |
| C même budget que D (600 s) | **5** (+ ft09, lf52) | [12 %, 51 %] |
| D tout exact (P0) | **11** | [39 %, 80 %] |

**Les deux parcours de CW-445 :**
- **(a) réparation progressive** : P1 0 → A 1 → *perception seule : non mesurée* → perception et règles **5** (+4) → et but **11** (+6).
- **(b) retrait d'un oracle** : tout oracle **11** → but rendu appris **5** (−6) → règles et perception rendues apprises, but gardé exact : **1** (−10).

**Causes pour A, sur 18 niveaux :**
- but absent : 10 ;
- théorie incompatible : 6 ;
- budget épuisé : 1 ;
- (1 niveau gagné).

**Pour B :** le but exact est **inexprimable** dans le langage de la théorie induite (« but absent ») dans 8 cas sur les 10 où D gagne.

**Les 7 niveaux que D ne gagne pas** sont tous en « budget épuisé », donc de **classe S** : bp35, sb26, sc25, sk48 (N1), r11l N2, tn36 N2, ar25 N3.

**3. Valeur de chaque maillon** (niveaux qu'il débloque parmi les 18)

| maillon | niveaux | lecture |
|---|---|---|
| **recherche (classe S)** | **7** | perdus même avec tout exact, à 600 s |
| **but** | **6** | dc22, tr87 et m0r0 N2 manquent de candidat atteint dans le budget ; re86 et lp85 ont un but supposé atteint sans victoire ; su15 n'a aucun candidat |
| règles et perception (ensemble) | 4 | A → C à 600 s : cd82, ls20, sp80, lf52 |
| perception seule | non mesurée | pas d'adaptateur objets exacts → induction |

- **Contrôles** :
  - tous les bras font au moins P1 (0 sur ces niveaux par construction) ;
  - **D vaut au moins P0 du pod** : 2 écarts, su15 et lf52, gagnés au Mac et pas au pod, parce que le Mac a 600 s contre 300 s et la recherche `paliers` en plus. C'est sous le seuil d'arrêt.

**4. Coût.** CPU seulement, Mac, 4 à 6 processus, environ 45 min de mur ; un niveau prend de 1 s (cd82) à 1 542 s (bp35). Aucun GPU, aucun LLM.

**5. Niveau de revendication.** Diagnostic sur 18 niveaux, une seule graine, une seule amorce. Il ordonne les chantiers ; il ne mesure pas un gain.

**6. Échecs d'exécution et configurations.**
- Deux faux départs : le chemin `PYTHONPATH` manquait, et la copie de l'enveloppe bouclait. Corrigés avant toute mesure, et rien n'a été compté.
- 5 bras ; la prédiction est vérifiée sur les 13 N1 :
  - **D 9**, hors de la prédiction 7 ± 1, parce que le Mac a 600 s et `paliers` en plus ;
  - C 3 ✓ ; B 1 ✓ ; A 1 ✓.
- **Hypothèse** : en partie vraie. Le but (6) pèse plus que les règles (4), **mais la recherche (7) pèse plus que les deux**.

**7. Incertitudes.**
- **La chaîne mesurée est celle du moteur de C, pas P1.** A gagne ft09 N1, que P1 perd. Il faudra écrire les crochets dans une copie de P1 pour mesurer P1 lui-même.
- **Budget égal en temps, pas en nœuds** : le vrai jeu copié coup par coup est bien plus lent que le programme compilé de D. Une partie des « budget épuisé » de C (dc22, tr87, m0r0) peut donc venir du simulateur et non du but.
- **B dépend du langage de la théorie induite** : « but absent » y veut dire « inexprimable », pas « mal choisi ».
- **Les 7 niveaux S** peuvent cacher d'autres maillons une fois la recherche résolue.
- ka59 N6 et g50t N8 ne sont pas mesurés.
