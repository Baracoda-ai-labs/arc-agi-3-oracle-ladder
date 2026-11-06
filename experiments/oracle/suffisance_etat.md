# Test de suffisance de l'état sur les traces P1 (F, CW-445 et CW-451) — 23/10, 14 h 10, Mac

**Question.** Pour une même clé d'état et une même action, observe-t-on plusieurs successeurs ?
- **Clé** : celle de l'exploration générique de P1 (image sans le bord, ni les pixels « compteurs »).
- **Traces** : paquet v2 (`experiments/films_p1/combo/fg_g0`, `fg_g1`), 20 publics, 38 niveaux joués.
- **Script** : `suffisance_etat.py`, résultats dans `suffisance_etat.json`.

**Résultat.**
- **Puissance** : 339 paires (clé, action) revues au moins 2 fois. Ce sont les seules qui peuvent se contredire.
- **24 sur 339 se contredisent (7,1 %)**, dans **4 jeux** seulement :
  - sc25 N1 : 16 sur 70 ;
  - ls20 N1 : 4 sur 20 ;
  - g50t N1 : 2 sur 2 ;
  - sb26 N1 : 2 sur 124.
- Les 16 autres jeux n'en ont aucune.

**Causes, dans l'ordre de CW-445, lues sur la différence entre les deux successeurs :**
1. **Jauge ou compteur collé au bord, mal masqué** :
   - sc25 : 8 pixels dans les colonnes 62 et 63 ;
   - sb26 : 2 pixels à (53, 60-61).
   - Le masque de P1 ne couvre qu'**1 pixel** de bord, plus les changements de 4 pixels au plus. → Variable minimale : **masquer une bande de bord de 3 pixels**.
2. **Compteur caché** : ls20, 68 pixels en bas de l'aire de jeu, une barre qui change sans que l'image d'avant diffère. → Variable minimale : **un compteur de pas** (rythme de la jauge, déjà mesuré par F : `economie_plan`).
3. **Mémoire de trajet** : g50t (fantôme qui rejoue le trajet). C'est connu, et la v4 le modélise déjà.
4. **Orientation ou dernière action** : sc25, 8 pixels au centre (le sens du joueur). → Variable minimale : **la dernière action**.

**Correctif 1, le moins cher : bande de bord de 3 pixels** (`combo_cle.py`, `CHRYS_F_CLE=bande3`).
- **Mesure** : sur le paquet v2, exactement comme la mesure combinée de C (films + nouveauté, 2 graines).
- **Contrôle sans drapeau** : il redonne `combo/fg_g*` **au coup près** (19 et 19 ; T4 101 et 102).

| banc | contrôle | bande3 | différence |
|---|---|---|---|
| 20 publics, graine 0 et graine 1 | 19 et 19 niveaux | **19 et 19** | 0 niveau, **0 perdu** ; **tn36 N1 gagné en 8 coups au lieu de 75 et 79** (h = 32) ; m0r0 N1 40 → 39 |
| T4 (104 jeux), graine 0 et graine 1 | 101 et 102 | **101 et 102** | identique au coup près |

**Verdict.**
- Le critère « +1 niveau » **n'est pas atteint**.
- C'est un **gain de score** sans perte : tn36 N1 passe de (32/75)² ≈ 18 % au plafond de 115 %. Cela fait environ **+0,17 point** pour le moteur seul sur 20 jeux, et 0 perdu sur les publics et sur T4.
- Le changement tient en 2 lignes (le masque).
- Les causes 2 et 4 (compteur de pas, dernière action) **ne sont pas testées**. Leurs jeux (ls20, sc25) sont perdus pour d'autres raisons : classe S, but.

**Limites.**
- Une seule définition de clé (celle de P1).
- La cause est classée automatiquement sur deux successeurs, puis vue à la main.
- Le gain tn36 repose sur 1 niveau.
