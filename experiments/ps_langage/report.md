> **Mise à jour 20/10 (CW-255, commit `8762746`)** : `psmoteur` corrigé (propriété de droite liée par son nom dans toute la
> règle, comme PuzzleScript). p107 82/82 et p137 127/127 : **177 jeux, 38 924 coups exacts sur 38 924, 852/852 fins** ;
> 175 jeux complets, p079 et p093 exacts jusqu'au plafond de 30 min. Les lignes ci-dessous décrivent l'état d'avant.

# Le langage décrit-il des jeux écrits par des humains ? Interpréteur PuzzleScript dans le langage (CW-241, session E)

## 1. Hypothèse et prédiction
- Question (décision de Thomas, CW-241) : notre langage (`chrysalide/arc3/langage.py`) décrit-il **exactement** des jeux
  écrits par des humains, indépendamment de nous ? Banc : 177 jeux PuzzleScript, 817 niveaux (`experiments/banc_ps/`).
- Méthode : **un seul programme du langage** (`interpreteur_ps.json`, 49 mots définis par macros, aucune fonction Python)
  interprète les règles de chaque jeu, lues comme une DONNÉE (analyse `psmoteur.Jeu` : règles, couches, légende, victoire,
  plus l'apparence des objets). Pas de programme par jeu.
- Prédiction écrite avant la mesure (CCM-144-B, B) : faisable en un jour pour motifs, directions, propriétés, `late`,
  `again`, `cancel` ; risques : **lenteur** des points fixes et **mots manquants**. Ce n'est pas une préinscription
  chiffrée au sens de `docs/preregistration/` (aucun entraînement ici).

## 2. Résultats (juge au pixel près contre le vrai moteur ARC du banc)
Critère de `experiments/T3.7/juge_t4.py` : image + sprites dessinés (nom, position, calque, pixels) + fins de niveau.
Par niveau : 30 coups au hasard (graine 1000 + k), puis la solution de `verite.json`. Les coups terminaux sont jugés comme
des fins. Population entière : aucun jeu n'est retiré.

| classe | jeux | coups exacts | fins justes |
|---|---|---|---|
| exact (jeu complet) | **173** | — | — |
| exact jusqu'au plafond de 30 min (p079, p093) | 2 | 627 / 627 | 8 / 8 |
| défaut du moteur de référence (p107, p137) | 2 | 194 / 209 | 5 / 5 |
| **total** | **177** | **38 909 / 38 924 (99,96 %, Wilson 95 % [99,94 ; 99,98])** | **852 / 852** |
| témoin « aucune règle » | 177 | 9 015 / 39 229 (23,0 %) | **0 / 856** |

- Fins à tort : 0. Erreurs d'exécution du programme : 0 (version finale).
- Les 15 coups faux viennent tous de p107 et p137. Le moteur de référence `psmoteur` y lève
  `Refus (propriété créée sans lien)` **en plein coup** (vérifié en le rejouant seul : p107 N0 coup 8 ; p137 N2 coup 1).
  `psmoteur` ne lie une propriété de la partie droite qu'à la même cellule de la partie gauche, alors que PuzzleScript la lie
  par son nom dans toute la règle. La vérité ARC est alors un état à moitié modifié. Ce n'est pas un manque du langage.
- Version : v1 pour 165 jeux ; v2 (mot `objets_dans_boite`, et correctif « sprite plus petit que la case ») pour les 12 jeux
  trop lents ou en erreur en v1. Commits `e2fdcc7` (v1), `5e28ef1` et `0718db0` (v2).

## 3. Comparaison appariée
- Contre le témoin « aucune règle », mêmes coups : 99,96 % contre 23 % des coups, 852 contre 0 fins. Le banc n'est pas
  à vide ; le témoin ne fait 100 % sur aucun jeu.
- Contrôle positif d'abord : p000 147/147, contre 32/147 pour le témoin.

## 4. Coût
- Processeur seul (Mac M5, partagé avec les campagnes de A et de B), un seul processus. Aucune API, aucun GPU, aucun LLM.
- Temps : v1 environ 4 h 30 pour 177 jeux, plafond de 10 min par jeu ; v2 environ 3 h pour 12 jeux, plafond de 30 min.
- Latence par coup, p95 par jeu : médiane 0,15 s ; pire jeu 24 s (p170). **La lenteur est le coût réel** : l'appariement
  des règles est interprété dans le langage, avec des points fixes sur tout le plateau.

## 5. Niveau de revendication
- **B** (mesure exécutable, contrôle positif, témoin, population entière, sur un banc externe de jeux humains) : le langage
  **décrit exactement** 175 jeux PuzzleScript sur 177 au pixel près. Les 2 autres sont des défauts du moteur de référence.
- **Limites** : ce banc est le sous-ensemble déterministe accepté par `psmoteur` (sans `random`, `rigid`, `...`,
  `startloop` ni temps réel). La complétude vaut donc pour ce sous-ensemble. Ce n'est pas un résultat d'article reproduit.

## 6. Échecs d'exécution et configurations explorées
- Configurations : v1 (sondes de pixels), v2 (`objets_dans_boite`). Il n'y a pas eu d'autre réglage, et aucun choix n'a été
  fait au vu des scores.
- Bugs trouvés en route, tous de E :
  - un passage relancé (premier passage arrêté sur p005, sans plafond de temps) ;
  - p126 : le joueur est dessiné sur 4 lignes, et la sonde lisait un pixel hors du dessin ; corrigé en v2.
- **Mot manquant trouvé** : les objets d'une case, transparents compris (`a` ne voit que les pixels opaques ; le filtre de
  `objets` est littéral). Il a été proposé (CCM-002-E), validé par B (CCM-159-B) et implémenté par A sous le nom
  `objets_dans_boite` (CCM-229/230-A). Gain : environ ×2 sur p005.
- Autres manques contournés sans mot nouveau :
  - l'application d'une fonction à une liste (`map`) : faite par `poser` et concaténation ;
  - l'affectation indexée : déjà connue, CCM-130-B.

## 7. Incertitudes
- Ordre d'insertion des objets dans une cellule : `psmoteur` suit l'ordre d'un dict, et l'interpréteur l'approche par
  l'ordre des calques. Cela ne compte que si deux objets d'une même cellule satisfont le même terme ; aucun cas n'a été vu.
- Fond retiré par une règle : l'interpréteur garde un fond implicite. Ce cas n'a été vu dans aucun coup jugé.
- Coups au hasard limités à 30 par niveau : les mécaniques rares hors solution sont peu sollicitées.
- API pour le chantier Dream : `expliquer.py` (CW-245), rejeu recalé. Elle reprend la même définition que
  `moteur.porte_partielle`.
