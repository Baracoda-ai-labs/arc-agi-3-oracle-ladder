# Diagnostic à 4 configurations (CW-224.1) : sélection FIGÉE le 18/10 à 23 h 45, avant toute correction

Règle : cette liste ne change plus, quels que soient les résultats. Une modification exige un nouveau fichier daté, avec sa raison.
Critères :
- niveau 1, donc accessible depuis RESET, sans préfixe ;
- résolu par P0 (règles exactes, pod, 1 000 000 / 600 s, `but` ou `paliers`) ;
- jeu non témoin ;
- plusieurs mécaniques et les deux modes d'interaction ;
- 4 des 6 niveaux ont montré des plans divergents au banc moteur seul (CCM-192-A).

| jeu | niveau | interaction | pourquoi lui | moteur seul (CCM-192-A) |
| --- | --- | --- | --- | --- |
| ft09 | 1 | clic | clics, couleurs ; but supposé faux (prévu « niveau » au dernier pas) | 858 coups, 72 plans divergents |
| tn36 | 1 | clic | 2ᵉ jeu à clic, autre mécanique | 10 coups, 2 plans |
| re86 | 1 | flèches | mobile décalé d'une case au 2ᵉ ou 4ᵉ pas ; mur supposé (CCM-086-C) | 148 coups, 50 plans |
| sp80 | 1 | flèches | rangée prédite au mauvais endroit au 3ᵉ ou 4ᵉ pas | 2 090 coups, 532 plans |
| ls20 | 1 | flèches | clé, jauge, occultation (AMODAL) ; « ne rejoue pas » 20 657 fois | 0 coup |
| tr87 | 1 | flèches | séquence et contraintes ; 0/30 transitions rejouées (perception, décor) | 0 coup |

Configurations à état initial contrôlé (même graine d'exploration, mêmes coups d'amorce) :
- **A** : règles induites + but inféré ;
- **B** : règles induites + but exact ;
- **C** : règles exactes + but inféré ;
- **D** : règles exactes + but exact. Si D échoue, c'est un bug d'adaptateur ou de budget, à régler avant toute lecture.

L'oracle (règles de `experiments/T3.1/regles/`, but exact) sert seulement au banc, jamais dans l'agent.
