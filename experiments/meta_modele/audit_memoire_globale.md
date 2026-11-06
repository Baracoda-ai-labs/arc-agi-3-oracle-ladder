# Audit de `docs/memoire_globale.json` (CW-365.5, B avec C) — 21/10, 21 h

## Ce que c'est
- **Fait par B le 18/10** (`scripts/memoire_globale.py`, commit `47289383`), à partir de `BIBLIOTHEQUE.md` (20 descriptions de jeux), d'`exhaustivite.json` et de T3.4. **Aucun témoin.**
- Quatre parties :
  - **`lois`** : 34 mécanismes (25) ou buts et défaites (9), avec un gabarit en pseudo-langage, la liste des jeux et la fréquence. 24 sont marqués « validée ». Les plus fréquents : jauge de coups 20/20, jauge épuisée 20/20, flèches et blocage 13, sélection par clic 10.
  - **`parametres`** : nouvelles classes par niveau, jeu par jeu.
  - **`strategies`** : 4 politiques, avec leur source.
  - **`classes`** : pour chacun des 20 jeux publics, la liste de ses mécanismes.

## Qui le lit
- **Aucun fichier du moteur** (`chrysalide/`) ne l'ouvre. Le constat de CW-365 est **confirmé**.
- Quatre scripts d'expérience le lisent : `T3.6/fiche.py` et `T3.6/strategie.py` (fiche et stratégie, 18-19/10), `T3.3/lot3.py` et `T3.0/carte_mouvement.py` (vocabulaire des classes). Ce sont des mesures, pas la chaîne réelle.

## Ce qui ne va pas, si on voulait en faire une mémoire du moteur
1. **C'est une VÉRITÉ sur les jeux publics, pas une mémoire apprise.** `classes` (les mécanismes de chaque jeu) et `parametres` sont tirés des descriptions et des programmes exacts. Un candidat qui les lirait **connaîtrait d'avance** la mécanique d'un jeu public. C'est interdit par la charte (« diagnostic séparé du candidat »), et cela ne servirait à rien sur les 110 jeux cachés.
2. **Seules les fréquences inter-jeux sont transférables** : « une jauge dans 20/20 jeux », « flèches et blocage dans 13/20 ». C'est un **a priori** légitime, déjà utilisé par l'ordre par fréquence (buts, mécanismes de C, fiches de E). Il est donc **déjà pris en compte ailleurs**.
3. **Format périmé** :
   - les gabarits sont en pseudo-langage, pas dans la langue unique (CW-348) ;
   - pas de statut au sens de LANGUE_PYTHON § 7, seulement un booléen `validee`, que la spécification interdit ;
   - antérieur au budget P2 et à l'ontologie v2.2-2.4.
4. **Aucune des propriétés d'un schéma de transfert (CW-365.5)** : ni observations qui le soutiennent, ni contre-exemples, ni domaine de validité, ni liaisons à réestimer. Les lois disent « tel jeu a tel mécanisme », jamais « un objet qui a joué le rôle de porte ».

## Ce que je propose (à trancher par Cowork ; aucun code changé)
- **(a) Garder le fichier comme ce qu'il est** : une **vérité de diagnostic** sur les publics. On le renomme ou on le marque ainsi, et la garde de lecture reste « jamais par le candidat ».
- **(b) Extraire les seules fréquences inter-jeux** vers l'a priori déjà en place. Cela évite un second ordre par fréquence concurrent.
- **(c) Transfert entre niveaux d'un même jeu, l'essai séparé de CW-365.5, après le point 1** : il ne part **pas** de ce fichier. Il part des **théories induites par le moteur lui-même** au niveau k :
  - une `Lecon` (LANGUE_PYTHON § 8), avec `provenance` (jeu, transitions), `limites`, `statut` et un rôle **paramétré par rôle et non par couleur** (`porte` = objet qui a eu le rôle `bouton(effet)` ou `solide` puis plus solide) ;
  - réaffectée au niveau k+1 par la liaison de C et D (CW-355).
  - **C** écrit l'extraction de la leçon depuis la théorie, **B** écrit le banc : niveaux k+1 avec et sans leçon, mêmes budgets, rien d'autre de changé, tous coups comptés.
