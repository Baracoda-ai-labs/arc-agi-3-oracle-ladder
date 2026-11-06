# SPDX-License-Identifier: MIT-0
"""C (CW-315) : un refus de rejeu devient un diagnostic (1re transition, classes, lois) et une correction gardée."""
import numpy as np

from chrysalide.arc3.logique.diagnostic import contradictions, corriger, diagnostiquer
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _traj():
    imgs = []
    for x in (1, 3, 5):  # un point de couleur 3 avance de 2 cases à chaque RIGHT
        g = np.zeros((8, 8), int)
        g[4, x] = 3
        imgs.append(g)
    return Trajectoire(imgs, [4, 4], ech=(1, 0, 0))


def test_diagnostic_et_correction():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0)})  # loi fausse : un pas de 1
    dg = diagnostiquer(th, tr)
    assert dg["t"] == 0 and dg["classes"] == [3] and "move(c3,a4,1,0)" in dg["lois"]
    assert ("move", 3, 4, (2, 0)) in dg["corrections"]
    th2, tr2, journal = corriger(th, tr)
    assert th2.moves[(3, 4)] == (2, 0) and journal[0][1] == ("move", 3, 4, (2, 0))
    assert rejeu(th2, tr2)[0] == 2 and diagnostiquer(th2, tr2) is None


def test_contradiction_signale_un_etat_incomplet():
    """Même image + même action → deux suites différentes (compteur caché) : signalé, images brutes identiques."""
    g0, g1, g2 = (np.zeros((6, 6), int) for _ in range(3))
    g0[2, 2] = g2[2, 2] = 3
    g1[2, 3] = 3  # 1er RIGHT : le point avance ; 2e RIGHT depuis la même image : il ne bouge pas (compteur caché)
    tr = Trajectoire([g0, g1, g0, g2], [4, 3, 4], ech=(1, 0, 0))
    c = contradictions(tr)
    assert len(c) == 1 and c[0]["action"] == 4 and c[0]["t"] == [0, 2] and c[0]["brut_identique"]


def test_corrections_ensemble():
    """Deux objets miroirs (pas +2 et −2) : chaque correction seule ne rejoue rien ; ensemble, tout rejoue."""
    imgs = []
    for k in range(3):
        g = np.zeros((10, 10), int)
        g[2, 1 + 2 * k] = 3
        g[6, 8 - 2 * k] = 5
        imgs.append(g)
    tr = Trajectoire(imgs, [4, 4], ech=(1, 0, 0))
    th = Theorie(moves={(3, 4): (1, 0), (5, 4): (1, 0)})
    th2, tr2, journal = corriger(th, tr)
    assert journal[0][1][0] == "ensemble" and rejeu(th2, tr2)[0] == 2
