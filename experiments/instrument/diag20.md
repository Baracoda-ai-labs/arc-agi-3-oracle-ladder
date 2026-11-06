# Diagnostic étendu aux 20 jeux publics non témoins (CW-249 action 1, CW-251) — nuit du 19 au 20/10, Mac, HEAD `d16584d`, K = 40, graine 0, niveau 1

Configurations (lettres de CW-230) :
- objets exacts + dynamique exacte + but exact (P0, contrôle) ;
- état perçu + dynamique exacte (B) ;
- perçu + induite + but exact (D) ;
- perçu + induite + but inféré (E, le système réel) ;
- dynamique exacte + but inféré (« règles exactes, but inconnu », CW-251).

Réglage : `CHRYS_AMODAL=1` seul. Les drapeaux postérieurs (COMPORTEMENT, MARQUEUR, BASCULE_FORME, BUT_STATIQUE) ne sont **pas** dans ce passage, d'où m0r0 et re86 non gagnés ici. Données : `diag20_k40_g0.json`.

## 1ʳᵉ défaillance par niveau 1 (règle d'ordre : solveur exact → perception → règles → but → exécution)
| classe | jeux | n |
| --- | --- | --- |
| **S** solveur (même à règles exactes, budget épuisé : 1 000 000 nœuds / 600 s) | ar25, bp35, g50t, sb26, sc25, sk48 | 6 |
| **M** modèle (règles) : amorce rejouée < 50 % | cd82 (19/40), ka59 (14/40), m0r0 (17/40), tr87 (0/40) | 4 |
| **M** modèle : plan sous but supposé démenti au 1ᵉʳ coup | ls20, sp80 | 2 |
| **G** but : aucun but planifiable, et but exact **inexprimable** même avec la démonstration | dc22, lf52, lp85, r11l, su15, tn36 | 6 |
| **P** perception : position fausse (t = 7 sur le chemin gagnant) | re86 | 1 |
| gagné par le système réel | ft09 | 1 |

Réserves :
- « S » sur ar25 signifie que le planificateur **à règles exactes** échoue, alors que MoteurC gagne ar25 N1 par ses règles induites : le programme exact est plus dur à explorer que la théorie de C.
- La configuration B (perception) est trop stricte sur les sprites de décor (`diag5.md`) ; seule la classe « position » est retenue comme P.
- La configuration C de CW-230 (objets exacts + dynamique induite) n'est pas encore là.

## Les 5 corrections les plus prometteuses (niveaux visés)
1. **Vocabulaire de buts** (G, 6 jeux : dc22, lf52, lp85, r11l, su15, tn36). C'est le seul cas où **même la démonstration gagnante** ne suffit pas à exprimer le but. Pistes : buts statiques de C (`CHRYS_BUT_STATIQUE`, 9/20 formes justes proposées), `victoires.json` de B. **C + B.**
2. **Planificateur à règles exactes** (S, 6 jeux : ar25, bp35, g50t, sb26, sc25, sk48). Transpositions et impasses (CW-249 action 2), union avec `paliers` et `compile_gpt`. g50t N1 est **la seule cible que Franzen rate au N1** (CCM-234-A). **C.**
3. **Perception pour l'induction** (M à amorce < 50 %, 4 jeux : cd82, ka59, m0r0, tr87). `COMPORTEMENT` de D a déjà débloqué m0r0 ; à mesurer sur cd82, ka59, tr87. **D.**
4. **Prise de main sous incertitude** (M au 1ᵉʳ coup, ls20 et sp80). Garde par aspect, consensus des k théories (CW-251) pour ne pas jouer un plan dont le 1ᵉʳ coup est déjà douteux. **A + C.**
5. **Sélection et marqueur** (P, re86). C'est fait par C (`MARQUEUR`, `SELECTION`) ; il reste re86 N2. **C.**

Échecs d'exécution : aucun (20/20 jeux mesurés).
