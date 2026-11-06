"""[G] ka59 N4, expérience HORS LIGNE (vrai jeu public) : le bloc c11 se pousse-t-il ? Jumeau poussé en zone basse
(R R R D), sélectionné au clic, puis amené contre le bloc par la droite (LEFT) et par le dessus (DOWN).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/experience_bloc_ka59.py"""
import os
import sys

import numpy as np
from scipy import ndimage

sys.path += [os.path.join(os.path.dirname(__file__), "../T3.0"), os.path.join(os.path.dirname(__file__), "../T3.1")]
os.chdir(os.path.join(os.path.dirname(__file__), "../.."))
import plafonds as pf  # noqa: E402

N = {1: "U", 2: "D", 3: "L", 4: "R", 6: "clic"}


def objs(g, cols=(14, 11, 5)):
    g, out = np.asarray(g), []
    for c in cols:
        lab, n = ndimage.label(g == c)
        for i in range(1, n + 1):
            ys, xs = np.nonzero(lab == i)
            out.append((c, int(xs.min()), int(ys.min())))
    return out


DEBUT = [(4, None, None)] * 3 + [(2, None, None), (6, 47, 29)]
for nom, suite in (("par la droite", [(2, None, None), (3, None, None), (3, None, None)]),
                   ("par le dessus", [(3, None, None)] * 3 + [(2, None, None)] * 2),
                   ("par la gauche", [(3, None, None)] * 5 + [(2, None, None)] + [(4, None, None)] * 2)):
    env, f = pf.env_au_niveau("ka59", 4)
    print("===", nom)
    for a in DEBUT + suite:
        f = pf.jouer(env, a)
        print("  ", N[a[0]], a[1:] if a[0] == 6 else "", objs(f.frame[-1]), f.levels_completed, f.state.name)
