# SPDX-License-Identifier: MIT-0
"""C (CW-321/324) : réserve de coups lue sur une barre de budget (une case perdue tous les 2 coups)."""
import numpy as np

from chrysalide.arc3.moteur import reserve_coups


def test_reserve_lue_sur_la_barre():
    grilles = []
    for t in range(21):
        g = np.zeros((64, 64), int)
        g[63, :40 - t // 2] = 15  # barre de 40 cases, une de moins tous les 2 coups
        g[20, 10 + t % 5] = 3     # un mobile, ailleurs
        grilles.append(g)
    r = reserve_coups(grilles, 20)
    assert r is not None and r["rythme"] == 2.0 and r["coups"] == 60 and r["marge"] == 4  # 30 cases restantes × 2


def test_pas_de_barre_pas_de_reserve():
    grilles = [np.zeros((64, 64), int) for _ in range(21)]
    assert reserve_coups(grilles, 20) is None
