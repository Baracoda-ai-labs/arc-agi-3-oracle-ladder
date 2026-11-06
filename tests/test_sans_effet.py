# SPDX-License-Identifier: MIT-0
"""C (CW-354.2, défaut de g50t N3) : une flèche vue SANS EFFET, d'une position donnée, alors que la théorie prédisait un
pas (mur invisible), n'est plus jouée d'ici, ni par la théorie, ni par le programme exporté. Drapeau éteint : rien."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import trouver_sans_effet
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _traj():
    xs = [1, 2, 3, 3, 2, 3, 3]  # en 3, RIGHT ne fait rien (mur invisible) ; ailleurs il avance
    acts = [4, 4, 4, 3, 4, 4]
    imgs = []
    for x in xs:
        g = np.zeros((6, 8), int)
        g[2, x] = 3
        imgs.append(g)
    return Trajectoire(imgs, acts, ech=(1, 0, 0))


def test_coup_sans_effet_retenu():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr, libre=False)[0] < len(tr.actions)
    trouver_sans_effet(th, [(tr, None, None)])
    assert {(a, pos) for a, pos, _ctx in th.sans_effet} == {(4, frozenset({(3, 3, 2)}))}
    assert rejeu(th, tr, libre=False)[0] == len(tr.actions)


def test_coup_sans_effet_exporte():
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_sans_effet(th, [(tr, None, None)])
    prog, non = exporter(th, (8, 6))
    assert not non
    p, sc = Programme(prog), Scene((6, 8), 0, 0, [_sprite(o) | {"visible": True} for o in tr.etats[0]])
    xs = []
    for a in tr.actions:
        p.step(sc, ({4: "RIGHT", 3: "LEFT"}[a],))
        xs.append(sc.sprites[0]["x"])
    assert xs == [2, 3, 3, 2, 3, 3]


def test_contexte_change_le_coup_redevient_permis():
    """CW-355 : le coup n'est interdit que dans le MÊME contexte ; si un objet apparaît ou disparaît sur la case d'arrivée,
    il redevient permis."""
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_sans_effet(th, [(tr, None, None)])
    un = frozenset({(0, 0)})
    m = ((3, un, 3, 2),)
    assert th.pas(m, 4, (8, 6))[0] == m                       # même contexte (case d'arrivée vide) : sans effet
    m2 = ((3, un, 3, 2), (7, un, 4, 2))                       # un objet sur la case d'arrivée : autre contexte
    assert th.pas(m2, 4, (8, 6))[0] != m2
