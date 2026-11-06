# G — CW-467.4 : deux contrôles du vérificateur (24/10, 00 h 35)

## (a) Rejeu des 40 coups : en chaîne ou transition par transition ?
**En chaîne.** `MoteurC.proposer` (`chrysalide/arc3/moteur.py:402`) appelle `theorie.rejeu(c, tr)` avec `libre=True`
par défaut (`chrysalide/arc3/logique/theorie.py:1032`) : le monde part de `traj.etats[debut]` (1ʳᵉ image de la fenêtre)
et n'est **jamais recalé** sur l'observation ; chaque prédiction part de la précédente. C'est le rejeu le plus strict
(il garde les objets cachés). La mesure « en chaîne » demandée n'a donc pas lieu d'être : c'est déjà le cas.

**Asymétrie à noter (pour l'autopsie de F)** : le **plan** ne part pas de l'état prédit au bout de la chaîne, mais de
`c.avec_selection(tr.etats[-1], …)` (`moteur.py:869`, chemin `planifier`), c'est-à-dire de l'état **perçu** sur la
dernière image. Ce qu'une image ne montre pas (trajet d'un fantôme, compteur caché, objet occulté) peut donc être juste
dans la chaîne de la porte et absent au départ du plan. Non mesuré : combien de 1ʳᵉˢ divergences en viennent.

## (b) Test de mutation entre branches
`experiments/G/mutation_branches.py` : pour s et A, `s1 = pas(s, A)` ; 3 marches aléatoires de 6 coups depuis s et s1 ;
puis `s2 = pas(s, A)` ; exigé `s2 == s1` et `s` inchangé (comparaison par valeur gelée, copie profonde avant).

| niveau | cas | essais | échecs |
|---|---|---|---|
| théorie (`Theorie.pas`) | g50t N1 déf. 2 (fantôme, retour : état à mémoire) | 200 | **0** |
| programme (`ProgrammeCompile` + `cloner`) | g50t N1 | 200 | **0** |
| programme | ka59 N4 (sélection au clic, glissade) | 200 | **0** |
| programme | re86 N5 (porteur, sélection, peinture) | 200 | **0** |
| **contrôle positif** : `cloner` qui partage l'état caché (`mutation_controle_positif.py`) | ka59 N4 | 200 | **181** |

**Lecture** : aucune mutation entre branches, ni dans la théorie ni dans le programme exporté, sur 800 essais ; le test
sait la détecter (181/200 quand on l'injecte). Les divergences de T1/H4 ne viennent donc pas d'un état partagé entre
branches de recherche sur ces cas. **Limite** : 3 jeux, marches aléatoires courtes ; les théories induites à la volée
dans P1 (fenêtre de 40) sont de la même classe `Theorie`, mais elles n'ont pas été testées une à une.
