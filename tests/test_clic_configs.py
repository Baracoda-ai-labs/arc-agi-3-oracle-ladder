# SPDX-License-Identifier: MIT-0
"""C (dc22 N3) : un clic sur un bouton fait basculer une configuration (pont horizontal ↔ vertical), sauf si un mobile
est sur les cases touchées ; un autre bouton échange les objets de deux plots."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import trouver_clic_configs
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _g(pont, joueur, plots):
    g = np.zeros((12, 12), int)
    g[0, 10] = g[0, 11] = 8          # bouton du pont (même couleur que le pont)
    g[3, 10] = g[3, 11] = 6          # bouton des plots
    if pont == "h":
        g[5, 2:5] = 8
    else:
        g[2:5, 3] = 8
    a, b = plots
    g[9, 1], g[9, 7] = a, b          # plots (objets d'une case)
    g[joueur[1], joueur[0]] = 3
    return g


def _traj():
    etats = [("h", (0, 11), (7, 5)), ("v", (0, 11), (7, 5)), ("h", (0, 11), (7, 5)), ("h", (0, 11), (5, 7)),
             ("h", (1, 11), (5, 7)), ("h", (1, 11), (7, 5))]
    acts = [("clic", 10, 0), ("clic", 10, 0), ("clic", 10, 3), 4, ("clic", 10, 3)]
    return Trajectoire([_g(*e) for e in etats], acts, ech=(1, 0, 0))


def test_bouton_bascule_et_echange():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0)})
    trouver_clic_configs(th, [(tr, None, None)])
    assert {r[1] == "echange" for r in th.clic_configs} == {True, False}
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr, libre=False)[0] == len(tr.actions)


def test_pont_bloque_par_un_mobile():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0)})
    trouver_clic_configs(th, [(tr, None, None)])
    m = tuple(o for o in tr.etats[0] if o[0] != 3) + ((3, frozenset({(0, 0)}), 3, 5),)  # joueur sur le pont
    assert th.clic(m, 10, 0) == m


def test_boutons_exportes_comme_la_theorie():
    """Programme exporté : mêmes images que les observations, coup après coup (pont, plots), et bouton sans effet quand
    le joueur est sur le pont."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0)})
    trouver_clic_configs(th, [(tr, None, None)])
    prog, non = exporter(th, (12, 12))
    assert not non, non
    k, o = 64 // 12, (64 - 60) // 2
    p, sc = Programme(prog), Scene((12, 12), 0, 0, [_sprite(x) | {"visible": True} for x in tr.etats[0]])
    for a, g in zip(tr.actions, tr.cases[1:]):
        p.step(sc, ("MOUSE", o + a[2] * k + 1, o + a[1] * k + 1) if isinstance(a, tuple) else ({4: "RIGHT"}[a],))
        assert (np.asarray(sc.image())[o::k, o::k][:12, :12] == np.asarray(g)).all()
