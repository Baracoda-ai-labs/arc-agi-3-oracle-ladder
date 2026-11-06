# G — rapport du 21/10 (recherche, exploration, appui au noyau logique)

## 1. Hypothèses et ce qui était attendu
- CW-351.4 : un guidage lu dans les relations de C (V1-B) aide la recherche sur les jeux à portes. **Non confirmé** : rien à lire hors g50t.
- CW-354/361 : re86 N5 et ka59 N4 jusqu'au plan gagnant réel (priorité de jeudi).
- CW-357/359 : liste d'`Experience`, témoin déterministe pour le test Qwen « où expérimenter ».
- CW-369/373/375 : appui au noyau ASP de C ; comparaison à temps égal.

## 2. Résultats, par cas (échecs comptés)
| cas | méthode | budget | résultat |
|---|---|---|---|
| g50t N1 (déf. 2, théorie de C) | V1-B (h_relations) | 300 s | sans plan (h 15 → 8, porte à tenir) |
| | macro_g gel 2 | 30 s mur | **20 coups, 0,7 s** |
| | A* guidé par le but | 60 s | sans plan (la distance trompe) |
| | noyau ASP de C | — | 16 coups, 52 s, gagné en réel |
| dc22, m0r0, sp80, sc25 | V1-B | — | non applicable (théorie sans but ni porte) |
| re86 N5 (dossiers de C) | macro_g, V0, 16 buts | 300 s | 0/16 ; **but `marques` exporté `false`** (corrigé chez C) |
| | sous-buts cumulés | 300 s | 7/8 marques ; géométrie : **≤ 6/8 à la fois** (7/8 hors grille) |
| ka59 N4, 2 cadres (diagnostic) | macro_g (+ clics sur la scène) | 300 s | sans plan |
| | sous-buts cumulés | 219 s | 18 coups ; programme « niveau » ; réel non franchi (croix manquante, attendu) |
| | **A* guidé par le but** | 0,08 s | **17 coups** ; programme « niveau » ; réel non franchi (attendu) |
| ka59 N4, 3 cibles + paire | macro_g / sous-buts / A* guidé | 300 / 900 / 300 s | sans plan |
| ka59 N4, théorie corrigée d'Astra | macro_g / sous-buts | 30 et 300 s | sans plan (2/3 au mieux) |
| | A* pondéré d'Astra | 0,2 s | 46 coups |

## 3. Comparaisons et lecture
- **Portefeuille** : macro_g gagne g50t (porte à tenir : la distance trompe), l'A* guidé gagne ka59 (partie atteignable). Ni l'un ni l'autre seul.
- **Les verrous étaient presque tous dans le modèle, pas dans la recherche** : but exporté faux (re86 `marques`), but trop permissif (`emboite` sans paire), jumeau non cliquable dans l'export, loi de poussée absente (ka59), clics figés sur l'image de départ (macro_g). Trouvés par des contrôles « le plan connu marche-t-il dans le programme ? » et par géométrie exhaustive.
- **Expériences dans le vrai jeu (hors partie)** : la poussée qui glisse et traverse la barre (ka59) a été découverte par un balayage + 3 coups-expériences ; C l'a apprise de ces observations.

## 4. Coût
CPU du Mac seulement ; aucun appel LLM ; ≈ 40 runs de 30 s à 900 s. Aucun coup réel dans une partie notée (tout hors ligne, jeux publics).

## 5. Revendication
Aucune (pas de victoire réelle par notre chaîne aujourd'hui ; ka59 N4 gagné par Astra, g50t N1 par le noyau ASP de C).

## 6. Échecs d'exécution, configurations explorées
- Bugs de mes bancs trouvés et corrigés avant rapport : issue « niveau » gardée entre sous-buts (8/8 faux, vu au rejeu réel) ; sous-buts qui perdaient la paire imposée ; listes d'arguments non découpées sous zsh (lots vides) ; clics mal formés dans un test manuel.
- Configurations : V1-B ×2 corrections, macro_g ±clics de scène ×2, sous-buts T_essai 20/60/150/300 s, A* poids 3.

## 7. Incertitudes
- ka59 N4, 3 cibles : la croix est-elle atteignable dans la théorie de C (loi d'Astra « glissade prolongée sur la barre » absente) ? Non vérifié.
- re86 : la forme des pièces perçues est probablement fausse (diagonales écrasées) ; non vérifié côté perception.
- Test Qwen « où expérimenter » (H, CCM-034-H) : le témoin de ressemblance égale ou bat Qwen sur 3 cas ; 4 cas seulement.

## Fichiers
`astar_but.py`, `banc_astar.py`, `banc_ka59.py`, `banc_re86.py`, `sousbut_re86.py`, `deux_files_re86.py`, `geometrie_re86*.py`, `but_marques.py`, `balayage_interactions.py`, `experience_pousse_ka59.py`, `experience_bloc_ka59.py`, `verite_selection.py`, `cas_exploration_g.py`, `temoin_ressemblance.py`, `verifier_plan.py`, `banc_dur.py`, `macro_g_astra_ka59.py`, `macro_g.py` (option `clics_scene`, défaut inchangé).
