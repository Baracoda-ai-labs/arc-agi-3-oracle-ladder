# T3.7 — Le LANGAGE décrit-il les mécaniques des jeux T4 ? (CW-203, session B, 18/10)

## 1. Question et critère
Prouver **par exécution**, et non sur le papier, que le langage des règles (v0.6, `docs/LANGAGE.md`) décrit chaque mécanique du générateur T4 (`CATALOGUE_INTEGRATION.md` § 6, plan point 1).
Critère, identique à celui des 20 jeux publics (`mesure_exhaustivite.juger`) : à chaque coup, l'image et l'état des sprites visibles (nom, position, calque, pixels) prédits par le programme doivent être **égaux au pixel près** à ceux du vrai moteur. Fins de niveau et défaites déclarées par le programme, contre le moteur.
Pas de prédiction chiffrée pré-enregistrée : c'est un contrôle d'expressivité, pas une mesure d'agent. Aucun entraînement, aucun LLM.

## 2. Montage
- **Deux programmes de FAMILLE**, un seul fichier pour tous les jeux d'une famille, et non un programme par jeu :
  - `regles/dedale.json` (95 ko, assemblé par `construire_dedale.py`, qui n'exécute rien : il écrit des termes du langage) ;
  - `regles/tuiles.json` (écrit à la main).
- **Données lues** :
  - plan du niveau = donnée `plan` du moteur (`donnees_de_niveau`), comme `cwU` / `elp` pour ft09 ;
  - **palette non visible au début du niveau** (couleur allumée de l'interrupteur, compteur plein, couleurs et formes de l'icône d'attribut) = section `niveau` `"*"`, injectée par le juge depuis `CONFIG` / `GABARITS` du jeu.
- **Coups joués**, par jeu et par niveau : 30 coups au hasard parmi les actions offertes (graine 1000 + k, arrêt à la fin du niveau ou à la défaite), puis la solution de `verite.json`. Une faute entraîne une resynchronisation sur le moteur, et la faute est comptée.
- **Jeux** : les 104 jeux générés (`T4_generateur.tgz`, 81 dédale, 23 tuiles), aucun exclu. Juge : `juge_t4.py`. Tableau : `tableau.py`.
- **Témoin** « aucune règle » (`--temoin`) : il mesure si le banc est à vide.

## 3. Résultats (population entière, aucun jeu retiré)
| famille | jeux | jeux exacts | coups non terminaux exacts | témoin vide | fins justes | fins à tort | défaites justes | erreurs |
|---|---|---|---|---|---|---|---|---|
| dédale | 81 | **81** | **13 306 / 13 306** | 3 517 (26 %) | 328 / 328 | 0 | 116 / 116 | 0 |
| tuiles | 23 | **23** | **1 953 / 1 953** | 1 337 (68 %) | 78 / 78 | 0 | 78 / 78 | 0 |

Intervalle de Wilson à 95 % sur la part de coups exacts : [0,9997 ; 1] (dédale) et [0,998 ; 1] (tuiles).

| mécanique (jeux) | décrite au pixel près | mots du langage employés |
|---|---|---|
| base dédale (81) : déplacement, murs, sortie, jauge | oui | `tant_que`, `libre` → `bloque` (mot), `placer` |
| pousser (38) | oui | test de la case suivante, `filtrer` / `empiler` sur l'état |
| clé-porte (23) | oui | `montrer`, état `cles` |
| gemmes (23), sortie fermée | oui | `montrer`, `recolorer` (compteur) |
| poursuivant (22) | oui | règle sans action (pas glouton vers le joueur), `si` |
| modificateur (19) : forme, couleur, rotation de l'icône | oui | `poser_motif`, `recolorer`, `tourner` |
| portail (19) | oui | téléportation conditionnelle |
| lave (17), défaite | oui | `perdre` |
| glace (16) : glissade | oui | `tant_que` borné |
| interrupteur et grilles (16) | oui | `montrer`, `recolorer` |
| recharge (16) | oui | état `g` remis à G + 1 |
| gravité (11) : chute des boîtes | oui | `tant_que` après l'action, `trier` |
| sélection (8) : SPACE change d'avatar | oui | état `sel` |
| trous (6), cibles (4) | oui | `filtrer`, `tous` |
| base tuiles (23) : clic, cycle de couleurs | oui | `case_clic`, `recolorer`, palette lue à l'écran |
| colonne (14), rangée (7) : décalage | oui | copie dans `etat` puis `recolorer` |
| verrou (14), lien (11), croix (8), cycle à 3 couleurs (1) | oui | `filtrer` des tuiles cibles |

**20 mécaniques T4 sur 20 décrites au pixel près**, sur les 104 jeux, avec un seul programme par famille.

### 3 bis. Mécaniques humaines ajoutées au générateur (CW-209, lot 1 : TIRER et CRÉATION, 8 jeux y200-y213)
Même programme dédale, étendu de deux blocs :
- **création** : passer sur un générateur crée une boîte sur sa case cible, une seule fois (mots `empiler` sur l'état des boîtes, puis `montrer`) ;
- **tirer** : après le pas, la boîte de la case quittée suit le joueur (effet conditionnel sur la case quittée).

| lot | jeux | jeux exacts | coups exacts | témoin vide | fins justes | défaites justes | erreurs |
|---|---|---|---|---|---|---|---|
| tirer (4) + création (4) | 8 | **8** | **1 584 / 1 584** | 410 (26 %) | 36 / 36 | 9 / 9 | 0 |

Les 8 jeux sont exacts du premier coup. Non-régression : les 81 jeux dédale d'origine, rejugés avec le programme étendu, restent **81/81 exacts** (13 306 / 13 306 coups).

## 4. Mots manquants et défauts remontés (à A)
1. **Défaut de l'interpréteur** : `["poser", n, []]` range la liste **littérale du programme**, puis `empiler` la fait grossir d'un coup à l'autre, ce qui a donné une palette et des copies de rangée fausses. Contourné ici par `["liste"]`. Correctif : copier la valeur dans `poser`.
2. **Conversion texte ↔ nombre** (`boite3` → 3) : absente. Contournée en identifiant un sprite par sa position ou par son rang dans l'ordre du niveau.
3. **`forme_modele` ne voit pas `GABARITS`** : `catalogue_moteur` ne lit que le dictionnaire `sprites` du module. Il s'agit d'une convention de lecture, pas d'un mot. Palette et formes injectées en paramètres.
4. **Affectation indexée de liste** (`l[i] = v`) : absente. Contournée en reconstruisant la liste avec `pour` + `empiler` (verbeux : c'est la principale raison des 95 ko).
5. `elem` sur un dictionnaire plante si la clé manque ; `table` (avec défaut) convient.
6. Ce banc ne juge pas la jauge dessinée (interface) : elle n'est **pas jugée**, comme pour les jeux publics sans canevas.

## 5. Coût
CPU du Mac seulement, environ 25 min pour les 104 jeux, plus autant pour le témoin. Aucun LLM, aucun GPU, aucun pod.

## 6. Niveau de revendication et limites
- **Revendication** : B, contrôle d'expressivité. Le langage décrit toutes les mécaniques présentes dans T4, et deux programmes génériques suffisent.
- **Ce n'est PAS** une preuve sur les mécaniques humaines absentes de T4 : création, tirer, annulation, longue portée, hasard, corps rigides, contraintes logiques, animations. Elles attendent l'ajout de Cowork au générateur (plan point 2).
- **Programmes écrits en lisant le moteur commun des jeux T4** : 400 lignes, identiques d'un jeu à l'autre, et les règles ne sont pas des témoins. Cela montre que le langage peut dire ces règles ; cela ne montre pas que l'induction les trouve.
- **Couverture** : solutions plus 30 coups au hasard par niveau, ce qui inclut les défaites (lave, poursuivant, jauge). Toutes les branches rares ne sont pas forcément exercées : chaîne de deux boîtes, portail occupé.

## 7. Incertitudes
- La part du témoin vide sur les tuiles (68 %) est élevée, mais le banc n'est pas à vide : seuil 99 %, et 0 fin de niveau sur 78 sans règles.
- Une seule exploration au hasard par niveau. Configurations explorées : 3 corrections du programme dédale (accès au plan, portail par la deuxième extrémité, identité des sprites) et 1 du programme tuiles (liste littérale).
