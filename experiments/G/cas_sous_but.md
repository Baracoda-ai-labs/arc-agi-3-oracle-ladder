# Cas « sous-but » pour la sonde (CW-346 / CW-347 point 7) — préparés par G, 21/10 11 h 10
Critère : la recherche de référence (`but`, 1 M de nœuds, 300 s CPU, programmes exacts `97f20c73`) épuise son budget,
alors qu'un plan existe (trouvé par `macro_g`, rejoué dans le vrai jeu). Les 4 cas sont 3 jeux différents + g50t.
**Vérité réservée à l'évaluateur** (jamais dans le dossier de Qwen) : la colonne « plan connu ».

| cas | but (`but`, échec) | plan connu (`macro_g`) | sous-but candidat qu'un évaluateur jugera utile |
|---|---|---|---|
| g50t N1 | 1 000 000 nœuds, 155 s | 17 coups : RIGHT ×4, SPACE, DOWN ×7, RIGHT ×5 | « un mobile sur la case colorée en haut à droite, puis relancer » |
| ar25 N1 | 925 293 nœuds, 309 s (temps) | 15 coups : DOWN ×10, LEFT ×5 | (à juger : la pièce pilotée au bord bas, puis vers la cible) |
| dc22 N2 | 1 000 010 nœuds, 225 s | 42 coups, 3 clics de bouton et des allers-retours | (à juger : l'ordre des 3 boutons) |
| m0r0 N2 | 1 000 153 nœuds, 92 s | 23 coups (deux pièces pilotées ensemble) | (à juger) |

**Mesure (CW-347.7), à calcul total égal** : temps de la question + recherche guidée par le sous-but, contre recherche
seule avec le même temps total. Branchement prêt côté G : `macro_g.chercher(..., texte=…)` accepte un programme dont la
condition de victoire est remplacée par le sous-but (phase 1), puis la vraie victoire depuis l'état atteint (phase 2,
mode « état fourni » du gel 2 `532fb79e`). Je l'écris si la sonde a le temps d'arriver à ce type.
**Fuites à éviter** (CW-347.5) : aucun nom de jeu ; pas de « fantôme », « dalle », « porte » ; les 4 cas de g50t
comptent comme une famille ; ici, g50t ne compte que pour un cas.
