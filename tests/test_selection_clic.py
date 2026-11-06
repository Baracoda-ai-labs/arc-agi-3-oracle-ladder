# SPDX-License-Identifier: MIT-0
"""C (ka59 N4, CCM-052-E) : deux objets de la classe pilotée ; les flèches ne déplacent que le sélectionné ; un clic sur
l'autre le sélectionne (CHRYS_SELECTION_CLIC)."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import trouver_selection_clic
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _traj():
    a, b = [1, 1], [5, 4]
    imgs, acts = [], []
    plan = [4, 4, ("clic", 5, 4), 4, 1, ("clic", 3, 1), 2]
    sel = a
    for k in range(len(plan) + 1):
        g = np.zeros((7, 9), int)
        g[a[1], a[0]] = 3
        g[b[1], b[0]] = 3
        imgs.append(g)
        if k == len(plan):
            break
        p = plan[k]
        acts.append(p)
        if isinstance(p, tuple):
            sel = b if (p[1], p[2]) == tuple(b) else a
        elif p == 4:
            sel[0] += 1
        elif p == 1:
            sel[1] -= 1
        elif p == 2:
            sel[1] += 1
    return Trajectoire(imgs, acts, ech=(1, 0, 0))


def test_selection_au_clic():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 1): (0, -1), (3, 2): (0, 1)})
    th.hors_jeu = tr.exclues
    trouver_selection_clic(th, [(tr, None, None)])
    assert th.selection_clic == (3, 1, 1)
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_sans_la_loi_les_deux_bougent():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 1): (0, -1), (3, 2): (0, 1)})
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr)[0] < len(tr.actions)


def test_selection_au_clic_exportee():
    """Programme exporté : mêmes positions que les observations, coup après coup (clic qui change la sélection)."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 1): (0, -1), (3, 2): (0, 1)})
    trouver_selection_clic(th, [(tr, None, None)])
    prog, non = exporter(th, (9, 7))
    assert not non, non
    k, ox, oy = 64 // 9, (64 - 9 * (64 // 9)) // 2, (64 - 7 * (64 // 9)) // 2
    p, sc = Programme(prog), Scene((7, 9), 0, 0, [_sprite(o) | {"visible": True} for o in tr.etats[0]])
    for a, g in zip(tr.actions, tr.cases[1:]):
        if isinstance(a, tuple):
            p.step(sc, ("MOUSE", oy + a[2] * k + 1, ox + a[1] * k + 1))
        else:
            p.step(sc, ({4: "RIGHT", 1: "UP", 2: "DOWN"}[a],))
        im = np.asarray(sc.image())[oy::k, ox::k][:7, :9]
        assert (im == np.asarray(g)).all()
