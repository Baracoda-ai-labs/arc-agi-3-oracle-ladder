# SPDX-License-Identifier: MIT-0
"""C (g50t N1) : complétion par l'avenir dès la 1re image — le sol sous le joueur est restitué au coup 0."""
import numpy as np

from chrysalide.arc3.logique.faits import completer_amodal, objets


def test_sol_complete_des_la_premiere_image():
    gs = []
    for x in (1, 2, 3):
        g = np.zeros((4, 6), int)
        g[1:3, 0:6] = 5      # sol (12 cases)
        g[1, x] = 2          # joueur posé sur le sol
        gs.append(g)
    etats = [objets(g, 0) for g in gs]
    out = completer_amodal(etats, gs, 0, futur=True)
    sol0 = [o for o in out[0] if o[0] == 5]
    assert len(sol0) == 1 and len(sol0[0][1]) == 12  # sans trou à l'image 0
    sans = completer_amodal(etats, gs, 0, futur=False)
    assert len([o for o in sans[0] if o[0] == 5][0][1]) == 11  # passé seul : le trou reste au coup 0
