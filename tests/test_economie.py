"""D (CW-321) : classement des indicateurs de bord — une barre qui raccourcit d'une case à chaque coup = budget, remise
au niveau ; une rangée de pastilles qui perd une pastille à chaque mort = vies."""
import numpy as np

from chrysalide.arc3.economie import classer


def _jeu():
    gs, evs = [], []
    reste, vies, x = 40, 3, 10
    for t in range(60):
        g = np.zeros((64, 64), int)
        g[63, :reste] = 4                  # budget : barre en bas
        for i in range(vies):              # vies : pastilles en haut à droite
            g[0:2, 56 + 3 * i:58 + 3 * i] = 8
        g[30, x % 50 + 5] = 2              # le joueur bouge au milieu
        gs.append(g)
        if t in (19, 39):                  # deux morts : budget remis, une vie de moins
            evs.append("mort")
            reste, vies = 40, vies - 1
        else:
            evs.append("coup")
            reste, x = reste - 1, x + 1
    return gs, evs[:-1]


def test_budget_et_vies():
    gs, evs = _jeu()
    ind = classer(gs, evs)
    etq = {tuple(i["boite"]): i["etiquettes"] for i in ind}
    budget = [b for b, e in etq.items() if "budget" in e]
    assert budget and all(b[1] == 63 for b in budget)
    assert any("vies" in e and b[1] <= 1 for b, e in etq.items())
