# Raccourcir les séquences de Franzen : précondition sur traces (F, CW-455 et CW-456) — 23/10, 16 h 30, Mac

**Question.** Les séquences d'actions explicites de Franzen ont-elles une version **moins chère** qui mène au même état final, avec une théorie étayée ? Si oui, combien de points cela vaut-il ?

**Arrêt prévu (CW-455)** : si la majorité des séquences n'a qu'une action, **ou** si les économies sont négligeables.

**Mesures** (18 passages R, Franzen pur, 20 publics ; transcriptions de R20, R21 et R22 au pod ; score officiel, qui reproduit 180/180) :
1. **Longueur des séquences**, sur 3 240 appels `action([...])` dans R20 à R22 :
   - 49 % des appels n'ont **qu'une** action ;
   - mais **80 % des actions** sont jouées dans des séquences de 2 ou plus.
   - Le premier critère d'arrêt n'est donc **pas** atteint.
2. **Borne haute du gain en score** : on suppose que **chaque niveau gagné** l'est au minimum de coups utile, c'est-à-dire au plafond officiel de 115 % (a = h / √1,15), avec les mêmes niveaux gagnés.
   - Résultat : **26,56 → 27,13, soit +0,57 point au plus.**
   - Cela vient de ce que Franzen gagne déjà ses niveaux sous la référence humaine (médiane h/a = 1,56), et que le score est plafonné.
3. **Coups « en trop »** : seulement **89 actions par passage** dépassent h dans les niveaux gagnés, soit **4,3 %** des 2 096 actions d'un passage.
   - L'économie de texte relu par Franzen (CW-456 a) est donc **au plus de quelques pour cent** du texte des retours d'action. C'est faible devant le reste du contexte, qui contient les images et le raisonnement.
4. **Niveaux en plus** : aucun à attendre. Les jeux de Franzen sont coupés par **l'heure** (19 jeux sur 20 dans R12), pas par la jauge. Moins de coups ne donne pas plus de temps de modèle.

**Verdict : arrêt, économies négligeables.**
- La borne absolue (+0,57) est sous 1 point, **avant même** de compter les faux raccourcis.
- CW-456 b le rappelle : le vérificateur en mode ombre avait trop de faux positifs. Une théorie induite trouverait moins que cette borne exacte.
- Le classement des coups des vies gagnantes en trois catégories (découverte, manipulation, détour) n'est pas fait : il ne peut pas changer la borne.

**Ce que cela confirme.** Le score de Franzen est limité par les **niveaux gagnés**, pas par les coups (CCM-040-F, UCB, exploration économe de C). Toute piste « moins de coups » vaut moins d'un point.

**Limites.**
- La longueur des séquences est comptée par motif dans les transcriptions. Le pic à 4 actions peut inclure des clics avec coordonnées : c'est une estimation.
- La borne ne tient pas compte d'un effet de vitesse via moins de texte. Il est majoré par les 4,3 % de coups en trop.
