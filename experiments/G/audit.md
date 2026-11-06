# Audit des arrêts (CW-304 étape 1) — 1ʳᵉ partie : 13 frontières, Mac, 20/10 soir
Recherche `but` de `plafonds.p0` (copie instrumentée `audit.py`, contrôle 5/5 nœuds et états égaux à p0), G allumé,
200 000 nœuds, 300 s CPU. Fichier : `audit_frontieres_200000_300.json`.

| niveau | arrêt | nœuds | états uniques / transitions | profondeur max | h0 → hmin | CPU s | simulation / clé / copie |
|---|---|---|---|---|---|---|---|
| bp35 N2 | temps | 148 030 | 0,067 | 4 | 2 → 2 | 300 | 82 / 12 / 6 % |
| dc22 N4 | **plan 65, gagné** | 92 583 | 0,026 | 64 | 53 → 3 | 60 | 79 / 14 / 7 % |
| g50t N1 | nœuds | 200 000 | 0,541 | 11 | 1 → 1 | 26 | 45 / 29 / 23 % |
| ka59 N4 | nœuds | 200 013 | 0,094 | 9 | 4 → 4 | 12 | 43 / 33 / 19 % |
| lf52 N3 | nœuds | 200 070 | 0,063 | 5 | 2 → 2 | 99 | 81 / 12 / 6 % |
| ls20 N4 | nœuds | 200 000 | 0,288 | 37 | 1 → 1 | 94 | 20 / 46 / 33 % |
| m0r0 N6 | nœuds | 200 312 | 0,005 | 6 | 2 → 2 | 58 | 7 / 62 / 30 % |
| re86 N5 | **plan 82, gagné** | 77 804 | 0,495 | 82 | 1 → 1 | 151 | 92 / 3 / 3 % |
| sc25 N5 | nœuds | 200 062 | 0,091 | 5 | 2 → 2 | 138 | 69 / 19 / 11 % |
| sk48 N2 | nœuds | 200 010 | 0,060 | 7 | 1 → 1 | 46 | 14 / 50 / 35 % |
| sp80 N4 | nœuds | 200 000 | 0,201 | 16 | 5 → 2 | 58 | 43 / 21 / 34 % |
| su15 N4 | nœuds | 200 008 | 0,573 | 5 | 2 → 2 | 222 | 78 / 10 / 10 % |
| tr87 N6 | nœuds | 200 000 | 0,791 | 10 | 4 → 4 | 196 | 22 / 33 / 43 % |
Aucun coup en erreur ; défaites seulement dans bp35 (656). L'heuristique compte < 2 %.
Référence (G éteint), même budget : dc22 N4 gagné en 123 s, re86 N5 en 240 s → **pas de victoire nouvelle due à G**.

## Lecture
1. **L'heuristique est plate** : sur 11 des 13 frontières, la distance au but ne baisse jamais (hmin = h0). La recherche
   « meilleur d'abord » devient une largeur à l'ordre d'insertion. C'est le défaut que vise l'étape 3 (dépendances du but).
2. **Le plafond de nœuds masque le gain** : 11/13 s'arrêtent au plafond de 200 000 nœuds bien avant 300 s (12 à 222 s
   de CPU). À temps égal sans plafond, la vitesse de G donnerait plus de nœuds → essai long demandé (CW-304) à faire.
3. **Redondance** : sur 7 niveaux, moins de 10 % des transitions mènent à un état neuf (m0r0 N6 : 0,5 %). Les coups sans
   effet (clics) coûtent une simulation chacun.
4. **Profondeur** : 4 à 16 sur 9 niveaux non gagnés ; les deux plans trouvés font 65 et 82 coups, profondeur atteinte
   seulement quand la distance baisse (dc22) ou par une file très étroite (re86).

## 2ᵉ partie : guidage lu dans la victoire (étape 3, essais), mêmes 13 frontières, même budget
- **Distance graduée** (`guidage.py`, `audit_frontieres_gradue_…`) : `existe` → minimum, `tous` → somme, écarts numériques,
  `non` poussé vers l'intérieur. Pente nouvelle sur g50t N1 seulement (72 → 48, sans plan). **0 victoire nouvelle.**
- **+ régression** (`audit_frontieres_regression_…`) : une variable cachée du but est remplacée par 1 + la distance aux
  conditions des règles qui la posent (2 niveaux de remontée). Pente sur sk48 N2 (3 → 2) et sp80 N4 (5 → 3). **0 victoire
  nouvelle**, 0 perte (dc22 N4 et re86 N5 restent gagnés).
- **Lecture** : sur 10 des 13 frontières, le but vaut 1 ou 2 conjoints booléens dont aucune remontée de 2 niveaux ne tire
  une pente ; ce que la recherche ne voit pas est en amont (quels objets bouger). Reste à essayer : l'ordre des actions
  par les dépendances (CW-304 point 3 tel qu'écrit : actions préférées en tête, les autres en file secondaire), et le
  test ×100 de cette nuit (CW-305) pour savoir si le budget seul ferait tomber un niveau.
- **+ ordre par dépendances** (`audit_frontieres_dependances_…`) : à distance égale, la transition qui change ce que lit le
  but (objets des filtres de la victoire et des règles productrices, variables cachées lues) passe en tête ; rien n'est
  élagué. 128 (tr87) à 135 845 (g50t) transitions préférées. **0 victoire nouvelle, 0 perte.**
- À budget de nœuds fixe (200 000), les trois guidages lus dans la victoire ne font tomber aucune frontière.
