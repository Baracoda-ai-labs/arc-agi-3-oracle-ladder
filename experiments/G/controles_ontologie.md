# CW-470 : contrôles structurels (SKOS / SHACL) — inventaire de G, page finale de J (24/10, 1 h 50) d'après l'autopsie de F

Diagnostic seulement, aucune migration (CW-470.4). Inventaire en lecture seule (46 contrôles existants), rangé en 4 couches ;
puis les 5 pistes de CW-470.3 : existe / partiel / absent. La colonne « défaut observé » sera remplie avec les 1ʳᵉˢ divergences
classées par F (colonne « structure / conversion / modèle / indéterminée »).

## 1. Contrôles existants, par couche (résumé)
- **(a) vocabulaire et classification** (≈ 10) : `tests/test_ontologie_formelle.py` (rôles fermés, clés de contrat,
  rivales départageables, transfert sans valeur de scène, `lit`/`ecrit` partout), `langue/roles.py:verifier_roles` (rôle, arité,
  statut), `theorie_contrats.py` (contrat cité existe), `menu_mecanismes.verifier` (mécanisme dans le menu), `traducteur.Refus`.
- **(b) schéma des objets, états, contrats** (≈ 8) : `arc3/langage.py` (`compiler_mots`, `_verifier_nom/_mots/_ast` au
  chargement ; termes inconnus seulement à l'évaluation), `export_langage._champs_inconnus` et liste `non_exporte` (refus du
  moteur si non vide, `moteur.py:414`), aller-retour théorie ↔ contrats, but intraduisible = `None` (plus de « faux » muet).
- **(c) sémantique des transitions** (≈ 18) : `theorie.rejeu` (en chaîne), `prediction.rejeu_contrat`, `verifier.verifier_loi`,
  `menu_mecanismes.verifier` (gagné / perdu), fidélité export = théorie = observation (`fidelite_export.py`, `fidelite_ka59_creux.py`),
  buts exportés = définition (`test_but_marques_export`, `test_contrat_buts`), indépendance (0 fausse sur 311 paires),
  non-contradiction U2/U3/U4/U6 sur les 20 programmes, simulateur compilé = interprète (`test_sim_rapide`), **mutation entre
  branches** (`mutation_branches.py`, 0/800, contrôle positif 181/200).
- **(d) induction et planification** (≈ 10) : MDL (`mdl.comprime`), garde des relations observées (`prediction.garder`),
  portes 1 et but (`moteur.porte`, `porte_but`), but supposé faux sur les états vus, réserve, porte de confiance
  (`confiance.py`), porte T1 `autorise` et vérification image par image, `verifier_plan.py`, `controle_passages.py`
  (empreintes, drapeaux, entonnoir, imputation, éteint = référence).

## 2. Les 5 pistes de CW-470.3
| piste | état | ce qui existe |
|---|---|---|
| références d'objets et de mécanismes résolubles | **absent** pour la théorie (classes et positions citées par `moves`, `solides`… jamais confrontées à la scène) ; noms de contrats seulement | assert de `theorie_contrats.py:79` |
| paramètres requis présents et typés | **absent** (`Theorie` = dataclass sans validation ; arité des rôles seulement ; `_nommer` laisse tomber des paramètres si la longueur diffère) | — |
| inconnu / faux / zéro | **partiel, local** (indépendance : inconnu = dépendant ; passabilité démontrée / bloquée / inconnue ; `cases_inconnues`) ; **contre-exemple** : `_champs_inconnus` traite `None`, `False`, `0` et vide comme « défaut » | — |
| provenance hypothèse / observation | **partiel** (`moves_supposes`, statut du but dans la porte T1, `SUPPOSES`/`VUS` côté Franzen) ; pas de provenance par fait ; garde de provenance des plans éteinte par défaut | — |
| cohérence des versions scène / théorie / plan | **absent** (empreintes de code seulement ; `VERSION` de l'ontologie lue par aucun contrôle) | — |

## 3. Défauts structurels déjà vus, indépendamment de l'autopsie
- **Phases incohérentes dans l'ontologie v1** (vérifié) : `PHASES` = {0 scène, 1 clic, 2 mouvement, 3 autonomes, 4 économie,
  6 issue…} mais `MECANISMES` met `deplacement`, `poussee`, `glissement` en **1**, `selection_clic` en **0**, `autonome` en **4** ;
  le test (`test_ontologie_formelle.py:39`) accepte tout entier ≤ 6 et ne peut pas le voir. Effet sur les rejeux : **aucun
  connu** (l'ordre d'exécution vient du langage, pas de ce champ) ; effet possible sur toute règle qui lirait `phase`
  (indépendance, traducteur). C'est exactement le genre d'erreur qu'une contrainte de forme (type SHACL) attrape.
- Budget codé en dur dans la porte T1 (`resource_margin = 150 - k - len(plan)`) ; MDL qui ignore une transition de forme
  différente sans la compter (`mdl.longueur_exceptions`).

## 4. Tableau final (sources : autopsie de F `experiments/oracle/autopsie/report.md`, 1ʳᵉˢ divergences H4/T1b ; qualification typée de J `experiments/J_reprise_but/report.md`)
| contrôle existant | défaut observé | contrôle manquant | test | coût | effet sur les rejeux |
|---|---|---|---|---|---|
| porte T1 (rejeu de la fenêtre) + image par image | déplacement prédit hors du terrain, réel immobile (21 H4 / 16 T1b) : **modèle empirique** (loi de blocage jamais observée) | aucun contrôle de forme : le schéma est respecté, la loi manque. Candidat empirique : « quitte la zone des changements vus » (15/21, 0/8 victoires, rétrospectif, F) ; `CHRYS_F_ZONE` a échoué sur les cas tenus à l'écart (CCM-063-F) | — | — | aucun par SKOS/SHACL |
| but supposé faux sur les états vus | but supposé atteint sans victoire (10 / 8) : **modèle empirique** ; J : 16 victoires prédites non observées en évaluation, dont **13 avec image déjà fausse** | aucun (rien ne distingue le but avant l'essai) ; la reprise après réfutation (J) : 0 niveau | `CHRYS_T1_REPRISE_BUT` | 6 bancs | 0 |
| idem | obstacle intérieur jamais heurté (4 / 3) ; changement non prédit (1 / 1) : **modèle empirique** | aucun | — | — | — |
| `test_ontologie_formelle.py` (phase ≤ 6) | `PHASES` ≠ phases des contrats (v1) : **structure**, vrai défaut, hors des divergences | contrainte « phase ∈ PHASES et cohérente avec ce que le contrat écrit » | corrigé par B (`9b4a04b7`, 49/49) | fait | aucun (aucun lecteur du champ) |
| `export_langage._champs_inconnus` | `None` / `False` / `0` / vide confondus (piste « inconnu / faux / zéro ») | distinction des trois valeurs | — | court | **aucun défaut observé** dans les rejeux : rien à faire avant le gel |
| empreintes de code (`controle_passages.py`) | `CHRYS_F_ZONE` codé hors `agent_p1`, non couvert par `code_sha` (B, CCM-321-B) | empreinte du paquet entier dans le journal (pas un schéma) | — | court | aucun sur les rejeux ; traçabilité |

**Conclusion : pas de chantier SKOS/SHACL avant le gel.** Aucune 1ʳᵉ divergence n'est structurelle ni de conversion ou
d'exécution (F : 0 sur 36/44 ; J : 0 `hors_plan`, 0 `prediction_impossible` sur 83 résultats d’intervention). Toutes relèvent du
modèle empirique (loi absente, but faux), que ni SKOS ni SHACL ne peuvent voir. Le seul défaut structurel vrai (phases)
est corrigé et n'avait pas d'effet. Après le concours (`PISTES.md`, CW-470.4) : SKOS pour noms, définitions, familles et
correspondances ; SHACL/pySHACL pour valider exports et échanges, générés depuis une source unique.
