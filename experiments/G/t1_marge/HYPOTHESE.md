# Bras « marge » de T1 (G, CW-457) — écrit AVANT la mesure, hypothèse née APRÈS lecture de T1b (déclaré)

**Origine (déclarée).** Dans les journaux de T1b sur T4 (CCM-073-G), la seule intervention de MoteurC qui coûte un niveau
(y014 N2, graine 0) est un plan de 14 coups autorisé avec `resource_margin = 16` (coups restants au budget du niveau
**après** le plan) ; les 4 victoires du moteur sur des jeux jamais vus laissaient au moins la moitié de la marge
(3/27, 2/28, 10/20, 7/103). C'est **un cas**, lu après la mesure : l'hypothèse n'est pas établie.

**Hypothèse.** N'intervenir que si `planned_actions ≤ resource_margin / 2` (mêmes champs que la ligne `autorise` de T1b)
évite les plans qui, s'ils divergent, ne laissent plus à P1 le temps de finir, sans retirer les plans gagnants.

**Changement unique.** `CHRYS_P1_MARGE=1` (absent = T1b au coup près) ajoute cette condition à `autorise` dans
`agent_p1/releve_moteur.py` d'une **copie** du paquet T1b (`4737d3ce`), `experiments/G/t1_marge/paquet`. Rien d'autre.

**Mesure.** Bras « joue » + marge, 20 publics et T4 (104 jeux), graines 0 et 1 ; références : T1b `joue2_*` de C et v2
(`films_p1/combo*`) ; contrôleur de B (`critere_gel_458`, artefacts).

**Prédiction chiffrée.**
- T4 graine 0 : y014 N2 **récupéré** (la référence v2 le gagne en 96 coups) ; les 4 victoires moteur sur jeux jamais vus
  **gardées** (y024 N1, y040 N2 en g0 ; y018 N2, y002 N1 en g1) ; net T4 ≥ celui de T1b (+3 g0, +6 g1).
- Publics : identique à T1b (ft09 N1-N3 g0, ft09 N1 g1 : plans de 2 à 5 coups, marges larges) ; 0 perdu.
- Pertes indirectes (mémoire inter-jeux, y030 N1) : non visées, peuvent changer dans les deux sens.

**Critère** (CW-458, contrôleur de B) : ≥ +1 niveau attribué au moteur, **0 perte imputable au moteur**, publics et T4
aux 2 graines. **Contrôle** : drapeau absent = T1b au coup près (un public court, ar25 et ft09, avant la mesure).
**Arrêt** : si y014 N2 n'est pas récupéré ou si une victoire moteur est perdue, le bras est rejeté.
