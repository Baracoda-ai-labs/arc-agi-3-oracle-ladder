# G — compilateur plus rapide des programmes ARC (CW-291) — RAPPORT (20/10, 18 h)

## 1. Hypothèse et prédiction
CW-291 : accélérer l'exécution du langage tel quel, 0 écart, cible ×2 à ×3 « sur tous les jeux ». Lien attendu (E,
CCM-014-E) : ×10 de vitesse ≈ +3 à +5 niveaux sur P0. Pas de pré-inscription formelle (pas d'entraînement) ; critères
de CW-291 : 0 écart sur les trajectoires, mêmes états visités, banc P0 apparié avec et sans.
Moyen retenu (CCM-001-G, validé CW-293) : **code Python généré par programme** (`chrysalide/arc3/sim_genere.py`), et non
tableaux numpy : lire un champ dans un tableau structuré coûte ×10 un dict, et le langage lit les objets un par un.

## 2. Ce qui est fait
- `ProgrammeGenere` (sous-classe de `ProgrammeCompile`) : termes et effets couverts traduits en expressions et instructions
  Python ; le reste garde la fermeture de `sim_rapide`. Sortie de boucle paresseuse des sous-termes invariants ; mots
  (macros) en ligne droite ; `pixel` lu dans une copie en listes ; mémoire des `objets(filtre)` d'un coup, vidée à chaque
  effet (copie rendue à chaque lecture : même sémantique d'identité).
- `cloner` et `cle_complete` à raccourcis exacts (clé de **même valeur** que `plan_langage.cle_complete`) ; option
  `CHRYS_BACKEND_TABLEAUX=2` : clé « plate », mêmes classes d'états, pas la même valeur.
- Interrupteur `sim_genere.installer()` (éteint par défaut), branché par A dans `plafonds.py`.

## 3. Contrôles (0 écart)
| contrôle | n | écarts |
|---|---|---|
| traces R0 des 19 jeux (exception, issue, image, clé à chaque coup) | 4 089 coups | 0 |
| recherche g50t N1, 20 000 nœuds, chaque coup rejoué par `ProgrammeCompile` | 20 000 coups | 0 |
| suite `test_langage.py` rejouée + cas propres (`tests/test_sim_genere.py`) | 117 tests | 0 |
| P0 `but`, 20 000 nœuds (nœuds, états, plan, issue dans le vrai jeu) | 60 niveaux | 0 (60/60) |
| clé plate : classes d'états contre `cle_complete` | 8 178 états | 0 |

## 4. Vitesse (temps CPU)
- Coup seul : ×1,8 en médiane sur 19 jeux (ls20, su15 ×3 ; tr87 ×18 à ×46 par la sortie de boucle et la mémoire `objets`).
  Copie ×1,9 ; clé ×1,3 (plate ×1,5).
- Nœud de recherche, P0 à 20 000 nœuds (Mac) : **×1,66 en médiane** (×1,07 à ×18).
- P0 pod, 1 M de nœuds, 300 s CPU, 3 bras mêlés, 24 processus : sur les 24 niveaux arrêtés par le temps, **nœuds explorés
  ×1,72** (G) et ×1,71 (G2) en médiane.

## 5. Banc P0 apparié (pod, `p0_but_1000000_300_pod.json`)
| bras | gagnés / 60 | + | − |
|---|---|---|---|
| ref | 27 | | |
| G | 27 | 0 | 0 |
| G2 (clé plate) | 27 | 0 | 0 |
Wilson 95 % pour 27/60 : [33 ; 58 %]. 38/60 niveaux identiques au nœud près (les 22 autres : plus de nœuds dans le même
temps, même issue). tr87 N6 (désigné par A) : 212 096 nœuds en 300 s CPU au Mac, pas de plan.

## 6. Niveau de revendication
Outil : simulateur ×1,7 plus rapide, 0 écart prouvé sur les bancs ci-dessus. **Aucun gain de niveaux** (D pour l'effet
sur le score). Cible ×2-3 non atteinte.

## 7. Coût, échecs, configurations
Pod : ≈ 40 min, 24 processus, 150 Go (au bord de la limite de 175 Go, CCM-278-A). Mac : contrôles. Un 1ᵉʳ lancement du
contrôle P0 bloqué (cause non trouvée, relancé avec traces par tâche) ; un défaut de `desinstaller` trouvé par le test et
corrigé avant mesure. Configurations explorées : 7 étapes successives, chacune contrôlée.

## 8. Incertitudes et limites
- La clé (linéaire en nombre de sprites, ≈ 1,4 µs par sprite) pèse maintenant 38 à 60 % d'un nœud. La seule voie connue
  pour la réduire franchement (clé incrémentale) est fermée (CW-278.4, accord de Thomas) ; non rouverte.
- Le Mac partagé (charge 12 à 17) rend les micro-mesures bruitées (± 20 %) ; les chiffres P0 sont en temps CPU.
- Le lien vitesse → niveaux semble plus faible qu'extrapolé : ×1,7 donne 0 niveau ; les niveaux non gagnés manquent de
  guidage plus que de nœuds (g50t, m0r0, sk48, sp80 épuisent leurs nœuds, CCM-273-A).
