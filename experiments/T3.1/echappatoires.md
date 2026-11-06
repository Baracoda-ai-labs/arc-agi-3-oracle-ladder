# T3.2 — Compte « sans échappatoire » des 20 jeux (2026-10-18, session B)

**Règle de décompte (proposée en CCM-078-B)** : une constante identique sur tous les niveaux du jeu (pas, couleur de rôle, tag de classe, catalogue de formes du jeu, borne de boucle) est **légitime**. Une donnée propre à un niveau (table indexée par le niveau, position en dur) ou un nom de sprite énuméré est une **échappatoire**.
Un mécanisme non écrit parce qu'absent des traces rend la traduction **incomplète**, sans être une échappatoire.
Source : la clé `contournements_restants` de chaque `regles/<jeu>.json`, classée à la main d'après cette règle (langage v0.3, banc honnête 18/19, 4 089 / 4 089).

| jeu | verdict | raison principale |
| --- | --- | --- |
| ar25 | **sans échappatoire** | restent des encodages de structure : accumulateurs, fermeture bornée à 13 passes (constante) |
| cd82 | **sans échappatoire** | géométrie de l'anneau et jauge de 100 constantes ; modèle reconnu à sa taille (heuristique) |
| g50t | **sans échappatoire** | pas, couleurs de rôle et jauge constants |
| r11l | **sans échappatoire** | appariements déduits (barycentre, couleurs), là où le moteur utilise les noms |
| sk48 | **sans échappatoire** | poussée itérative, instantanés UNDO par clés |
| su15 | **sans échappatoire** | catalogue des 9 fruits et 3 ennemis (constante du jeu) |
| sb26 | sans échappatoire, à confirmer | clé absente ; reste un motif vert 6×6 constant |
| dc22 | sans échappatoire, **incomplet** | grue, cycle de couleur, indicateurs des niveaux 4-5 non écrits |
| ft09 | sans échappatoire, **incomplet** | clignotement du niveau 0 non écrit |
| re86 | sans échappatoire, **incomplet** | murs, jauge et défaite non écrits |
| sp80 | sans échappatoire, **incomplet** | réussite du versement non modélisée |
| ka59 | échappatoire | poussée déroulée sur 3 rangs, fausse pour une chaîne plus longue ; explosifs non décrits |
| lp85 | échappatoire | table niveau → cycles |
| ls20 | échappatoire | cran de jauge par niveau |
| m0r0 | échappatoire | table de 4 noms → sens du miroir |
| sc25 | échappatoire | maximum de jauge par niveau, 2 noms d'interrupteurs, sorts choisis par nom d'icône |
| tn36 | échappatoire | tables des onglets par niveau |
| tr87 | échappatoire | graines d'aléa par niveau, recopiées du moteur |
| lf52 | échappatoire, banc à vide | plans des 10 niveaux recopiés, clic approché |
| bp35 | pas de traduction | `Scene` ne dessine pas le HUD où vit le jeu (step() conforme sur l'état interne seulement) |

**Score : 7/20 sans échappatoire et complets** (ar25, cd82, g50t, r11l, sk48, su15, plus sb26 à confirmer). **11/20 si l'on admet les traductions incomplètes.**
Les 7 échappatoires de lp85, ls20, m0r0, sc25, tn36, tr87 et ka59 sont presque toutes des **données cachées par niveau**. Les mots `donnees_de_niveau`, `attr_cache` et `segment` de la v0.3 (CCM-100-A) devraient en lever la plupart : c'est la prochaine passe, à un seul sous-agent (plafond CW-120).
Réserves :
- classement fait par B, sans second avis ;
- « légitime » reste un jugement : r11l et cd82 tiennent sur des heuristiques justes pour les niveaux joués ;
- les traces ne couvrent pas tous les niveaux. Les contrôles au hasard contre le moteur couvrent tous les niveaux pour ls20, sk48 et ar25, mais seulement les niveaux 0-2 pour g50t.
