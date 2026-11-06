# ARTICLE-ROP5-5x2 — rapport E1 (4/11/2026)

**Préinscription** : `ARTICLE_ROP5_TEMOINS_04.md`, commit 7bee8cc8 (réf. `refs/e1/article-rop5-temoins-04`), gelée avant la location.
**Code** : e1/temoins f54bb6a1. Le lanceur `temoins_rop5.sh` (sha256 d81c42c3…) reprend la chaîne de l'essai 2 RO et y ajoute la porte P5 de ROP5 v9 / ABBA P5.
**Manifeste** sha256 43853dc3…, écrit avant tout jeu témoin. Il est identique à l'essai 2 pour :
- Franzen 10882e33 ;
- les poids d1b06032… ;
- le harnais 38d19662… ;
- 10 flux et 48 min par jeu.

Les drapeaux P5 effectifs sont lus dans env.txt.

## 1. Prédictions (gelées) et verdict
1. Moyenne des 10 cases ≤ 42,98 ; prévision ponctuelle 38. **Observé : 45,50 → prédiction réfutée.**
   - C'est +2,52 sur RO essai 2, et l'écart reste descriptif (autre jour, autre instance). Il est bien inférieur au bruit inter-passages : RO va de 41,55 à 44,42, ROP5 de 40,50 à 50,50.
2. Niveaux attribués au moteur P5 : 0 dans les deux passages. **Observé : 0 et 0 → confirmée.**
3. Le moteur ouvre au départ sur chaque jeu, et au moins une fois de plus dans au moins 3 jeux sur 5 par passage. **Observé : départ 10/10 ; réouvertures 3/5 (TM1) et 5/5 (TM2) → confirmée.**

## 2. Résultats par case (scores natifs ; aucune case manquante)

| Passage | Jeu | ROP5 | Niveaux | Actions | RO essai 2 |
|---|---|---|---|---|---|
| TM1 | vc33 | 100,00 | 7/7 | 244 | 75,00 |
| TM1 | tu93 | 67,72 | 8/9 | 256 | 44,06 |
| TM1 | s5i5 | 77,78 | 7/8 | 279 | 27,78 |
| TM1 | cn04 | 4,76 | 1/6 | 150 | 47,62 |
| TM1 | wa30 | 2,22 | 1/9 | 517 | 13,27 |
| TM2 | vc33 | 100,00 | 7/7 | 205 | 53,26 |
| TM2 | tu93 | 66,59 | 8/9 | 298 | 66,22 |
| TM2 | s5i5 | 27,78 | 4/8 | 220 | 41,67 |
| TM2 | cn04 | 4,76 | 1/6 | 109 | 47,62 |
| TM2 | wa30 | 3,37 | 2/9 | 379 | 13,33 |

- **Moyenne par passage** : TM1 50,50 et TM2 40,50 (RO : 41,55 et 44,42). **Moyenne des 10 cases : 45,50** (RO : 42,98).
- **Moyenne par jeu, ROP5 contre RO** : vc33 100,00 / 64,13 ; tu93 67,16 / 55,14 ; s5i5 52,78 / 34,72 ; cn04 4,76 / 47,62 ; wa30 2,80 / 13,30.
- **Victoires complètes** : 2 (vc33, dans les deux passages) ; RO n'en avait aucune.
- Actions totales : 1 446 et 1 211. Détail par case dans `cases.csv`.

## 3. Ce que la porte P5 a fait (traces `porte_v5`, fin de chaque ouverture)

| Passage | Ouvertures | dont départ | dont stagnation | Coups du moteur | Niveaux du moteur |
|---|---|---|---|---|---|
| TM1 | 8 | 5 | 3 | 23 (1,6 % des actions) | 0 |
| TM2 | 11 | 5 | 6 | 31 (2,6 %) | 0 |

- Fins d'ouverture : « non gagné » 18 fois, « défaite » 1 fois (tu93, TM2). **Aucune panne de protocole.**
- Le moteur a joué au plus 12 coups par jeu et par passage, et n'a gagné aucun niveau.
- **Les écarts avec RO ne lui sont donc pas attribuables.** Ils viennent du LLM, qui joue plus de 97 % des coups. La porte ne change que le contexte : quelques coups « (auto) » et des fenêtres de stagnation.
- Détail par jeu dans `porte5_temoins.txt`.

## 4. Coût et durée
- Instance Vast 59148667 (Idaho, RTX PRO 6000 WS, 193 Go RAM, 1,739 $/h disque compris).
- Louée à 19:04:30 UTC et détruite par la garde à ≈ 21:34, juste après le dépôt de RAPATRIE. La console affiche ensuite 0 instance et 0 volume.
- **Dépense facturée : 6,18 $**, bande passante comprise, pour un plafond de 7 $. Crédit : 10,99 → 4,82 $.
- Déroulé :
  - installation de 19:13 à 19:23 ;
  - CTLP5 de 19:24 à 19:35 ;
  - TM1 de 19:55 à 20:43 et TM2 de 20:43 à 21:31, chacun en 48 min, code 0.

## 5. Niveau de revendication
- **D (descriptif)**. Il y a 2 passages, une seule instance, et la comparaison avec RO se fait d'un jour à l'autre.
- La seule affirmation solide est négative : **le moteur P5 n'a gagné aucun niveau sur les jeux témoins.**

## 6. Écarts et échecs d'exécution
- **CTLP5** : contrôle court de 6 min sur g50t, ka59 et re86 (jeux publics non témoins), coût ≈ 0,3 $. Il a été accepté par Cowork comme écart déclaré. Résultat : 3 ouvertures, 637 coups du moteur, 0 panne.
- **20 min de pod inactif** (≈ 0,6 $) : le manifeste était prêt à 19:35, mais ma surveillance ne l'a pas vu, et AUTORISE_TM1 n'a été posé qu'à 19:55.
- **Garde** : le test local avec un faux curl a été refusé par permission et n'a pas été contourné. Il a été remplacé par un préflight GET de la clé d'instance sur le pod (HTTP 200). La destruction autonome a ensuite fonctionné.
- **Tentatives** : 1 seule, aucune relance de case.

## 7. Incertitudes
- Avec 2 passages, le bruit domine : s5i5 donne 77,78 puis 27,78 dans la même configuration.
- La victoire répétée sur vc33 et l'effondrement de cn04 (47,62 → 4,76) ne peuvent pas être imputés à la porte, puisque le moteur n'y gagne rien. Ils relèvent probablement de la variance du LLM ou de l'effet de contexte des coups « (auto) ». Ce test ne permet pas de trancher.

Archives : `pod.tgz` (sha256 5cd9ba6d…, identique pod/Mac), `tm1.tgz` (b4156639…), `SHA256SUMS` (827 fichiers).
