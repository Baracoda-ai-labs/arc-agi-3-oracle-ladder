# Audit du méta-modèle des 20 jeux publics (CW-321 / 322 / 323) — session B, 20/10, 23 h 10

**Question** : pour chaque jeu public, les 7 cases du méta-modèle sont-elles (a) **dans le jeu**, (b) **dans notre programme exact** (`T3.1/regles`), (c) **apprises ou utilisées par le moteur** ?
Données : `audit.json` (par jeu, avec la lecture complète) ; scripts `audit.py` et `audit_programmes.py` ; lectures `lecture_*.json`.

## Méthode
- **(a) jeu** : lecture du code source des 20 jeux non témoins (témoins exclus avant ouverture), par 5 lecteurs en parallèle (4 jeux chacun, lecture seule, sans calcul), à partir de l'inventaire de Cowork (`inventaire_cowork.json`). Pour chaque affichage : ce qu'il représente et sa règle exacte. Pour chaque `lose()` : sa cause.
- **(b) programme** : un compteur d'état est-il cité par une règle `perdre` ? Vérifié règle par règle.
  - **Correction de l'inventaire** : le comptage des mots `consommer` et `epuise` ne suffit pas. ls20 écrit `["poser", "epuise", …]`, et 5 autres programmes tiennent un compteur `coups` ou `jauge` qui mène à `perdre`.
- **(c) moteur** : lecture du code du moteur (`moteur.py`, `faits.masque_cases`, `masque.py`, `logique/ressource.py`, attributs P10).
- **T4** : `CONFIG`, `NIVEAUX` et le code partagé des 104 jeux générés.

## Ce que montre l'audit
| case | (a) dans le jeu | (b) dans notre programme exact | (c) moteur |
|---|---|---|---|
| **Économie : budget de coups** | **20 / 20** (barre affichée dans 20 / 20 ; 3 fois en sprite simple, sans `RenderableUserDisplay` : g50t, sc25, tn36) | **6 / 20** (cd82, g50t, lf52, lp85, ls20, sk48) | **non** : la jauge est masquée ; seule `ressource.py` (ls20, hors chaîne principale) la lit |
| Économie : vies | 3 / 20 (ls20 : 3 vies affichées ; sp80 : 4 versements ratés, cachés ; r11l : 5 contacts de danger, cachés) | 2 / 3 (ls20 `vies`, sp80 `versements`) | non |
| Économie : recharge dans le niveau | 2 / 20 (ls20 : cases qui remettent 42 ; sc25 : objet qui rend 10 actions) | 1 / 2 (ls20 `rech`) | non |
| Économie : minuteur | 2 / 20 (bp35 : plafond qui descend ; ka59 : bombes à retardement) | 0 / 2 | non |
| **Défaite** | **20 / 20** ; épuisement du budget dans **19 / 20** (ls20 : perte de la dernière vie) ; autres causes : contact 3 réelles (bp35 plafond, g50t ennemi ou écrasement, r11l danger ; ka59 = code mort), piège 1 (bp35 pointes), chute 1 (dc22), autre 3 (sp80 5e versement, su15 plus de fruit, lf52 code mort) | **10 / 20** ont une règle `perdre` | contact seulement (`mort`, exportée en `perdre`) |
| Interface | budget 20 / 20 ; progression 2 (lp85, tn36) ; vies 1 (ls20) ; autre 7 (rotation d'écran sp80, carte ar25, brouillard ls20, chute dc22…) | dessinée en partie (ls20, g50t, sb26, sc25, tn36, tr87…) | **masquée en bloc** |
| Niveaux | **rien ne persiste** d'un niveau au suivant dans 20 / 20 (budget remis, vies remises). Deux détails : le compteur affiché de lf52 ; l'orientation de l'avatar de sc25 | — | transfert sous drapeau (D) |

## Trous, par nombre de jeux touchés
1. **Budget de coups non décrit : 14 jeux** (ar25, bp35, dc22, ft09, ka59, m0r0, r11l, re86, sb26, sc25, sp80, su15, tn36, tr87). C'est le trou n° 1. Dans tous ces jeux, un plan trop long perd au vrai jeu.
2. **Défaite hors budget non décrite : 3 jeux** (dc22 chute, r11l contact, su15 « plus de fruit »).
3. **Minuteur non décrit : 2** (bp35, ka59). **Vies non décrites : 1** (r11l, compteur caché). **Recharge non décrite : 1** (sc25).
4. **Pièges pour la perception (D, C)** :
   - **lf52 : le compteur affiché n'est PAS celui qui fait perdre.** L'affiché compte aussi l'annulation et persiste entre niveaux ; un compteur caché fait perdre à 64, 320 ou 640 ;
   - sp80 et r11l ont un **compteur de vies caché**, sans affichage ;
   - sp80 **fait tourner l'écran** de 180° aux niveaux 2, 3 et 5 : la barre passe en bas ;
   - g50t, sc25 et tn36 dessinent la barre comme un **sprite ordinaire**, hors `RenderableUserDisplay`.

## Règles exactes du budget (pour C : `etat[n]`, `consommer`, `epuise`)
- Ce qui coûte **varie selon le jeu**, et c'est l'information utile au planificateur :
  - toute action (cd82, m0r0, r11l, bp35 annulation comprise) ;
  - mouvements seulement (sk48, tr87, re86 ; le clic est gratuit dans sk48) ;
  - clics comptés seulement (ft09 : clic hors grille ou non gagnant ; lp85 : clic de bouton ; tn36 : tout clic) ;
  - barème (dc22 : mouvement 1, bouton 2, chute 20 ; su15 : fusion interdite 2+2×pénalité ; ls20 : 1 ou 2 par mouvement selon le niveau).
- **Le coup gagnant est souvent gratuit** : il est testé avant le décompte dans ar25, dc22, ft09, ka59, lp85, re86, sc25, su15 et tr87.
- **Budgets par niveau** : de 13 (lp85 N1) à 1 024 (dc22 N6). Les valeurs exactes sont dans `audit.json`, champ `lecture.economie`.

## Colonne T4 (104 jeux générés, 397 niveaux)
- **Budget `G` dans les 397 niveaux** (6 à 116 coups, médiane 34). Épuisement = défaite (`statut = -1`) dans les deux familles, dédale (319 niveaux) et tuiles (78).
- Autres défaites : **lave** (17 jeux) et **contact d'un poursuivant** (22 jeux). Recharges (`recharges`, remettent G+1) dans **16 jeux**. Les pastilles sont dessinées comme « indicateur / compteur » ; leur sens exact n'est pas vérifié.
- `verite.json` ne décrit ni jauge, ni vies, ni défaite (CW-322) : **la vérité de l'économie T4 est dans le code partagé**, pas dans `verite.json`.

## Conséquences
- **A, G** : les plans à règles exactes ignorent le budget dans **14 jeux**. Ils restent vrais au jeu, puisqu'ils sont rejoués, mais ils peuvent **perdre des niveaux gagnables** par excès de longueur.
- **C** : priorité n° 1, le budget comme état, avec **le barème propre au jeu** et le coup gagnant gratuit ; puis la chute (dc22) et les contacts (r11l, g50t, bp35). Premier test : re86 N5 (budget 250).
- **D** : la classification des indicateurs a ici sa vérité, avec 20 barres de budget, 2 de progression et 1 de vies. Attention aux pièges de lf52 et sp80.

## Incertitudes
- Les lectures sont faites par des lecteurs automatiques, sur des fichiers parfois énormes (ka59 41 000 lignes) : des règles fines ont été lues rapidement. Chaque lecture garde ses réserves dans `lecture_*.json`, champ `incertain`.
- « Dans le programme » ne dit pas si le budget **y est juste** (valeur, barème). Une vérification par rejeu est à faire.
- bp35 a une règle `perdre`, mais elle n'est pas reliée à un compteur : sans doute les pointes ou le plafond, à vérifier.
