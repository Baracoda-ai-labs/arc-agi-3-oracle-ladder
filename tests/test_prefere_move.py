# SPDX-License-Identifier: MIT-0
"""CW-451 (C) : `prefere_move` — une classe déclarée autonome qui suit TOUJOURS la flèche jouée devient contrôlée ; un
vrai poursuivant (bouge sans flèche, ou contre le sens) reste autonome ; rien d'autre ne change."""
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import prefere_move
from chrysalide.arc3.logique.theorie import Theorie


def _traj(deplacements, actions):
    """Objet c5 de 4 × 4 px sur un fond 0 avec décor fixe (échelle 4 lisible) ; `deplacements` en cases, un par coup."""
    def image(x, y):
        g = [[3 if min(i, j) < 4 or max(i, j) >= 60 else 0 for i in range(64)] for j in range(64)]
        for i in range(8, 15):
            for j in range(1, 15):
                if (i * 7 + j * 3) % 5 == 0:
                    for k in range(4):
                        g[4 * i + k][4 * j:4 * j + 4] = [2] * 4
        for k in range(4):
            g[4 * y + k][4 * x:4 * x + 4] = [5] * 4
        return g
    x, y, grilles = 3, 3, []
    grilles.append(image(x, y))
    for dx, dy in deplacements:
        x, y = x + dx, y + dy
        grilles.append(image(x, y))
    return Trajectoire(grilles, actions)


def test_suit_la_fleche_devient_controle():
    tr = _traj([(1, 0), (1, 0), (0, 1), (-1, 0), (0, -1)], [4, 4, 2, 3, 1])
    th = Theorie(autonomes={5: None})
    th2 = prefere_move(th, [tr])
    assert 5 not in th2.autonomes and th2.moves[(5, 4)] == (1, 0) and th2.moves[(5, 2)] == (0, 1)


def test_vrai_poursuivant_reste_autonome():
    bouge_sans_fleche = _traj([(1, 0), (1, 0), (1, 0)], [5, 5, 5])        # bouge à chaque SPACE : pas une flèche
    contre_le_sens = _traj([(1, 0), (-1, 0), (1, 0)], [3, 4, 3])           # va à droite quand on joue gauche
    for tr in (bouge_sans_fleche, contre_le_sens):
        th = Theorie(autonomes={5: None})
        assert prefere_move(th, [tr]).autonomes == {5: None}
