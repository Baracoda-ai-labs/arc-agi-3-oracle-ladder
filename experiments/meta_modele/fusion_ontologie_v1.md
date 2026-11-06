# Fusion de l'ontologie formelle v1 — comparaison préparée par B (22/10, 1 h 10, CW-382 / CW-386)

Deux v1 indépendantes, même découpage (relecture d'Astra) :
- **B v1.2** : `chrysalide/langue/ontologie_formelle.py` (Python déclaratif, dans le dépôt), 21 tests verts ;
- **agent cloud** : `experiments/defi_llm/agent_cloud/livraison_boucle/ONTOLOGIE_V1.md`, avec son code `boucle/`, que **je n'ai pas lu**. Elle a été **éprouvée sur ka59 N1–N5**, gagnés d'une traite.

Cowork fusionne (CW-382.2). B convertit ensuite en Python et passe le test de non-contradiction, ce qui vaut adoption (CW-382.3).

## Ce que la v1 de l'agent cloud apporte, et que B n'a pas (à reprendre)
1. **Numérotation des phases de `next`** : 0 scène → 1 clic → 2 mouvement et poussée → 3 autonomes (horloge) → 4 économie → 9-10 rendu, qui ne touche aucun fluent. B avait des numéros contrat par contrat, sans table. **On reprend la sienne.**
2. **Étage « projection » (rendu)** : `Trou` (marqueur ou passager), `RegleRendu` (indice paramétré par direction), `CompletionScene` (sol sous l'occultant, appris pixel à pixel), et HUD exclu des comparaisons de géométrie. Mes deux « règles de perception » en sont un sous-ensemble.
3. **Catalogue des types d'écart**, avec leur signature calculable et les hypothèses générées : TRAVERSEE, BLOCAGE, DISTANCE, AUTONOME, RENDU, SCENE, DECOR, INCONNU, CERTIFICAT. Il **manque complètement chez B**. C'est le cœur de la boucle qui apprend.
4. **Coûts MDL** des patchs (bloquant 2, poussée 2, prolongation 3, paramètre 3, fond 9), puis expérience discriminante en cas d'égalité, bornée par la jauge.
5. **Contrat `Piston`** (autonome périodique : direction, période, phase, charge, portée). Chez B, `autonome` restait générique.
6. **État latent** : `sel`, `porte` (passager vivant) et l'horloge `t` modulo le PPCM des périodes, reconstruits par rejeu. Et la règle « l'image n'est pas l'état ».
7. **Connaissances transférées `K`**, sans coordonnées, avec un exemple réel de fin de N5. C'est ce qu'il faut pour l'essai « transfert entre niveaux » (CW-367).
8. **Leçon de compilation mesurée** : ASP multi-shot stratifié 0,1 s, contre 39 à 64 s en un seul coup non stratifié.

## Ce que B apporte, et que l'agent cloud n'a pas (à garder)
1. **Liste fermée des rôles** (`ROLES_ONTOLOGIE`, 12 rôles, avec descriptions et coup qui départage) et **statut par rôle**. Chez l'agent cloud, les « rôles des couleurs » sont une option libre.
2. **Économie MESURÉE sur 20 publics et 104 T4** (CW-324 P2, `budget_reel.py`, 346/367) :
   - actions gratuites selon le jeu (su15, ar25, ft09, T4 tuiles) ;
   - coûts différents de 1 (dc22, su15) ;
   - seuils différents de 0 (sc25, m0r0) ;
   - recharges (sc25, T4).

   L'agent cloud a une jauge **apprise par régression sur ka59 seul**, et `defaite_a_zero` « jamais testée ». **On garde le barème paramétré de B**, avec la régression comme manière de l'apprendre en partie.
3. **Non-contradiction vérifiée** : U2 (fin exclusive) et U3 (une ancre) sur 20 vrais jeux et 20 programmes exacts ; U5 (défaite terminale), 8/8 sur R0 ; solidité globale réfutée, 16/20.
4. `victoire_prime` comme option **mesurée** (9/20). L'agent cloud n'a qu'une « convention prudente ».
5. **Contrats absents chez l'agent cloud** : ramassage, transformation (modificateur), bouton (avec tenue), téléportation, création, minuteur.
6. **Vies** comme option détaillée (nombre, cause, effet, recharges), avec les jeux concernés (ls20, r11l, sp80).

## Les deux points qui se contredisent (à trancher par Cowork)
1. **Défaite de la jauge** : l'agent cloud la tient pour « hypothèse a priori, jamais testée ». B l'a **mesurée** dans 20 jeux sur 20 ; le seuil et le coût varient. → **Proposition** : `defaite_epuisement` est confirmée dans tous les jeux mesurés, et seul le barème reste à apprendre.
2. **`fond_solide`** (« le fond bloque tout ») : c'est une option chez l'agent cloud. Chez B, le blocage dépend du mode (glissement ou marche) et de l'obstacle. → **Proposition** : `fond_solide` devient un cas particulier du contrat `blocage`, avec obstacle = fond, sans option à part.

## Forme proposée pour la v1 fusionnée
- Un seul fichier, `chrysalide/langue/ontologie_formelle.py`, dont les étages sont : **protocole** (avec la table des phases de l'agent cloud) / **état latent** / **contrats de mécanismes** (union des deux) / **économie** (barème de B) / **projection** (agent cloud) / **types d'écart** (agent cloud) / **options de domaine**.
- La correspondance des noms vers le code `boucle/` de l'agent cloud et vers `economie.lp` de F est écrite **dans le fichier** (une seule source de noms).
- Tests : cohérence et non-contradiction (déjà en place). On y ajoute un test « chaque type d'écart génère au moins un contrat existant ».
