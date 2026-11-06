# SPDX-License-Identifier: MIT-0
"""Pièce poussée qui glisse (ka59 N4, CCM-041-G) : sous selection_clic, le sélectionné avance sur une autre pièce de sa
classe ; elle glisse par pas, au plus glisse[0], à travers les classes traversées, s'arrête devant un obstacle ; le
sélectionné ne bouge pas."""
from chrysalide.arc3.logique.theorie import SEL_CLIC, Theorie

P = frozenset({(0, 0)})


def test_glisse():
    th = Theorie(moves={(14, 2): (0, 1)}, selection_clic=(14, 0, 0), glisse=(4, frozenset({15})))
    monde = ((14, P, 0, 0), (14, P, 0, 1), (15, P, 0, 3), (9, P, 0, 9), (SEL_CLIC, frozenset(), 0, 0))
    apres, bouge = th.pas(monde, 2, (1, 10))
    assert bouge and (14, P, 0, 0) in apres and (14, P, 0, 5) in apres  # 4 cases au plus, à travers la barre 15
    obstacle = ((14, P, 0, 0), (14, P, 0, 1), (9, P, 0, 3), (SEL_CLIC, frozenset(), 0, 0))
    apres, _ = th.pas(obstacle, 2, (1, 10))
    assert (14, P, 0, 2) in apres  # s'arrête devant l'obstacle 9
