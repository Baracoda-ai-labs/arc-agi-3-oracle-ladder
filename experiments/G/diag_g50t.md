# Diagnostic de g50t N1 (CW-315, les 6 causes) — 1ʳᵉ partie, 20/10 soir (Mac)
Jeu : boucle temporelle. Le joueur (couleur 9) enregistre son trajet ; SPACE le renvoie au départ, et un fantôme rejoue
le trajet. Les mobiles posés sur des dalles ouvrent des portes (dalle → fil → porte). Une jauge (sprite `ppfvilwwnk`, 1×64)
recule d'un pixel tous les 2 coups ; jauge vide = défaite. Victoire : centre du joueur = centre d'une sortie, jauge non vide.
Recherche `but` (G allumé), états en file sérialisée (`G_COMPACT=1`, 0 écart).

| cause | constat | verdict |
|---|---|---|
| clé de déduplication | sans la jauge ni `coups`, les 108 185 états de 200 000 nœuds tombent à 44 170 (×2,4). Mais une dominance « même état, plus de jauge = mieux » (ressources monotones détectées par marche au hasard : la jauge et `coups`) n'écarte que 3 025 états à 200 000 nœuds, et 10 297 à 1 M : le meilleur d'abord rencontre en général d'abord l'état le plus coûteux | **pas le levier** |
| variable d'état manquante | trajet du joueur gardé (`etat.trajet`, `attrs.trajet`) : nécessaire, puisque le fantôme le rejoue. Rien de manquant vu | à vérifier contre le moteur |
| branches équivalentes | 54 % de transitions vers un état neuf ; peu de doublons | non |
| horizon trop long | profondeur max 11 à 200 000 nœuds, **13 à 1 M** (540 944 états, 1,4 Go). Facteur de branchement effectif ≈ 2,7 : atteindre une profondeur de 30 demanderait ≈ 10¹³ états | **cause principale probable** |
| heuristique trompeuse | distance graduée : de 72 à 48 (joueur vers la sortie la plus proche). Elle ne voit pas qu'il faut d'abord un fantôme sur une dalle pour ouvrir la porte | **probable** (à démontrer : la sortie la plus proche est-elle derrière une porte ?) |
| impasse irréversible | la jauge borne la partie à ≈ 128 coups ; pas d'autre impasse vue | non pour l'instant |
| but incomplet | non vérifié : le code du jeu est obscurci ; la règle a passé le rejeu des trajectoires de Franzen, qui n'a jamais gagné N1 | **reste à vérifier** |

Suite : (1) démontrer la cause « heuristique » (la porte entre le joueur et la sortie) ; (2) sous-buts lus dans le programme
(porte ouverte ⇐ mobile sur la dalle ⇐ fantôme ⇐ trajet enregistré, puis SPACE) ; (3) vérifier le but contre le moteur.

## 2ᵉ partie : g50t N1 a un plan de 17 coups (vérifié dans le programme ET dans le vrai jeu)
Plan joué à la main (diagnostic à règles exactes, pas une victoire du moteur) : `RIGHT ×4` (le joueur va sur la dalle,
la porte s'ouvre), `SPACE` (retour au départ ; le fantôme rejoue les 4 pas et finit sur la dalle), `DOWN ×7` (par la
porte, rouverte quand le fantôme arrive), `RIGHT ×5` → **niveau gagné au 17ᵉ coup**. Le programme et le moteur restent
identiques coup par coup (positions du joueur et du fantôme, porte), et l'issue « niveau » tombe au même coup.
- **But incomplet : non.** Règles : justes sur ce plan.
- **Heuristique trompeuse : démontrée.** Le coup indispensable (`SPACE`) renvoie le joueur au départ : la distance au but
  remonte (graduée : de ≈ 48 à 72), donc le meilleur d'abord explore d'abord tous les états proches de la sortie,
  porte fermée.
- **Horizon** : 17 coups, contre une profondeur max de 13 à 1 M de nœuds. Le niveau est « S » par la recherche, pas par
  le modèle.
- Ce qu'il faudrait que la recherche voie : la porte entre le joueur et la sortie, la dalle qui l'ouvre, et que seul
  un fantôme peut la tenir pendant que le joueur passe. C'est une chaîne de sous-buts lisible dans le programme
  (règle des tics : « avancent sur le sol hors porte fermée » ; « dalle → fil → porte »).
- Nouveauté seule (`iw1`, `iw2` de `plafonds`, 3 M de nœuds, ≈ 450 s) : **pas de plan** (2,5 M et 1,9 M d'états).
  La largeur de nouveauté ne suffit pas non plus à atteindre les 17 coups.
- BFWS (CW-318, famille 3 ; `audit.py`, `G_RECHERCHE=bfws`) : priorité (nouveauté parmi les états de même distance,
  distance), rien n'est élagué ; faits = position et apparence des sprites, attributs et variables cachées atomiques,
  **ressources monotones exclues** (sinon la jauge rend tout état « nouveau »). Largeur 1 et 2 (paires de faits qui
  diffèrent du départ), distance avec régression, 1 M de nœuds : **pas de plan** ; profondeur 129 atteinte (la
  recherche file en profondeur sans trouver la combinaison dalle–SPACE–porte).
- Bilan provisoire : ni le meilleur d'abord (plat ou gradué), ni la nouveauté (iw1, iw2, BFWS 1-2) ne trouvent le
  plan de 17 coups dans 1 à 3 M de nœuds. Reste à voir : l'approfondissement itératif d'A (bras « profondeur » du ×100),
  et des sous-buts lus dans le programme.
