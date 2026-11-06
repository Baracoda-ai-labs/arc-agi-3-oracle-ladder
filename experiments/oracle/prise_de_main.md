# Où le moteur v2 peut-il ajouter des points à Franzen ? (F, CW-452) — 23/10, 14 h 30, Mac

**Données**
- **Franzen pur** : 18 passages R du pod (R5 à R22 ; R14 à R22 lus dans `/workspace/runs`), 20 publics, score moyen **26,56**.
- **Moteur v2** : le paquet du gel (P1 + films + nouveauté), 2 graines (`experiments/films_p1/combo/fg_g0`, `fg_g1`).
- **Score officiel** : min(115, (h/a)² × 100) par niveau, pondéré, plafonné. Il reproduit 180/180 scores R (CCM-040-F).
- **Script** : `experiments/oracle/prise_de_main.py`.

## 1. Tableau par niveau (v2 gagne aux 2 graines, sinon « c »)
- **(a) v2 gagne, Franzen perd** le plus souvent : g50t N3, N4 ; ka59 N2, N3, N4 (plus g50t N5–N7 et ka59 N5, que Franzen n'atteint jamais).
- **(b) les deux gagnent** :
  - v2 joue **moins** de coups que Franzen sur **g50t N1 (22 contre 39) et ka59 N1 (11 contre 22,5)** seulement ;
  - ailleurs v2 joue **plus** : ar25 N1 37 contre 18,5 ; lp85 N1 16,5 contre 8 ; r11l N1 41 contre 7,5 ; sp80 N1 83 contre 11,5 ; tn36 N1 77 contre 27,5 ; m0r0 N1 40 contre 27.
- **(c) perdus par les deux** : 65 niveaux atteints par Franzen.

**Score moyen par jeu, Franzen contre v2 seul** :
- g50t : **4,96 contre 100** ;
- ka59 : **6,62 contre 53,57** ;
- ailleurs Franzen domine (ar25 54 contre 8 ; lp85 62 contre 3 ; r11l 33 contre 2).

## 2. Gain en score selon la règle de prise de main

| règle | décidable en direct ? | gain sur 20 publics | hors g50t et ka59 |
|---|---|---|---|
| v2 au début des niveaux (a), prudente (Franzen s'arrête où il s'arrêtait) | non (il faut connaître le jeu) | +0,63 | — |
| v2 sur les niveaux (b) où il joue moins | non | +0,13 | — |
| **moteur d'abord**, au plus K coups par niveau, main rendue au 1ᵉʳ échec | oui | K = 100 : **+4,97** ; K = 10 à 40 : −0,3 à −0,7 | **−0,3 à −2,4** (perte) |
| **porte v4** : à chaque niveau, la v4 regarde la scène ; elle garde la main tant qu'elle reconnaît **et** gagne ; sinon ses coups de sonde (0 à 4) s'ajoutent à Franzen, qui garde la main jusqu'à la fin | **oui** | **+7,06** | **−0,04** (coût de la sonde) |

## 3. Lecture
- **Tout le gain vient de g50t et ka59**, les deux jeux où la v4 reconnaît la scène.
- Ce sont aussi **les deux jeux pour lesquels ses boucles ont été écrites à la main** (M15) : le +7 n'est donc **pas** une preuve de gain sur les jeux cachés de Kaggle.
- La règle « porte v4 » a un **coût presque nul ailleurs** (−0,04 sur les 18 autres jeux), parce que le score est plafonné et que Franzen gagne ses niveaux à h/a ≈ 1,56 en médiane. **Son espérance sur Kaggle est donc ≥ −0,05**, avec un gain si des jeux cachés relèvent des familles que la v4 reconnaît.
- Sa vraie valeur se lira sur les témoins (27/10) ou sur Kaggle, pas sur les publics.
- Une prise de main **sans porte** (moteur d'abord sur tous les jeux) **fait perdre des points** dès qu'on retire g50t et ka59 : à rejeter.

## 4. Recommandation
**Critère CW-452 (≥ +1 point sur les 20 jeux) : rempli pour la porte v4 (+7,06), avec la réserve ci-dessus.**
- **Variante à préparer (A, avec D)** : Franzen inchangé ; au début de chaque niveau, la v4 du paquet v2 regarde la scène (CPU, 0 à 4 coups de sonde). Elle joue tant qu'elle reconnaît et gagne. Au premier refus ou échec, la main revient à Franzen pour le reste du jeu.
- **Mesure au pod** : elle sert de **contrôle d'intégration**. Attendu : environ +7 sur les publics si le branchement est juste. Le vrai test est Kaggle ou les témoins.
- **Coûts à vérifier dans le harnais** : CPU du moteur (g50t N5 = 47 s, sinon moins de 2 s par niveau), et l'historique de Franzen après des niveaux joués par le moteur (il reprend dans un niveau qu'il n'a pas vu).

**Limites**
- 2 graines pour v2.
- Les coups de sonde sont lus dans les parties v2. Pour un niveau que v2 n'a jamais atteint, la sonde est supposée de 2 coups.
- Le modèle « Franzen reprend tel qu'il était » ignore l'effet sur son contexte.
- Score sur 20 publics, pas sur les 25 jeux de Kaggle.
