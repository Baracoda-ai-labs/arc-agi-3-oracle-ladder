# SPDX-License-Identifier: MIT-0
"""E (CCM-054/055-E), écrit par C : but « emboîter » — chaque cible creuse (fragments réunis) porte en son centre le centre
d'une pièce ; même verdict dans la théorie et dans le programme exporté (CHRYS_BUT_EMBOITE)."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import but_emboite
from chrysalide.arc3.logique.theorie import Theorie

UN = frozenset({(0, 0)})
ANNEAU = frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1)}


def _monde(px, py):
    # cible creuse coupée en deux fragments (comme à l'échelle 3), une pièce d'une case
    haut = frozenset(z for z in ANNEAU if z[1] == 0)
    bas = frozenset((x, y - 1) for x, y in ANNEAU if y > 0)
    return ((4, haut, 5, 5), (4, bas, 5, 6), (3, UN, px, py))


def test_emboite_theorie_et_cibles():
    g = np.zeros((12, 12), int)
    for x, y in ANNEAU:
        g[5 + y, 5 + x] = 4
    g[1, 1] = 3
    tr = Trajectoire([g, g], [4], ech=(1, 0, 0))
    th = Theorie(moves={(3, 4): (1, 0)})
    but = but_emboite(th, [(tr, None, None)])
    assert but == ("emboite", ((12, 12),), (3,))
    assert not Theorie._vrai(but, _monde(1, 1))
    assert Theorie._vrai(but, _monde(6, 6))


def test_emboite_exporte():
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    but = ("emboite", ((12, 12),), (3,))
    th = Theorie(but=but)
    prog, non = exporter(th, (12, 12))
    assert not non
    for px, py in [(1, 1), (6, 6), (7, 6), (9, 9)]:
        sc = Scene((12, 12), 0, 0, [_sprite(o) | {"visible": True} for o in _monde(px, py)])
        Programme(prog).step(sc, ("UP",))
        assert (getattr(sc, "issue", None) is not None) == Theorie._vrai(but, _monde(px, py)), (px, py)


def test_emboite_paire_imposee():
    """CCM-044-G : une cible-moule n'accepte que la classe de son objet (une pièce 14 dans la croix du bloc 11 : faux)."""
    from chrysalide.arc3.logique.theorie import Theorie
    piece = (14, frozenset((x, y) for x in range(3) for y in range(3)), 9, 9)
    bloc = (11, frozenset((x, y) for x in range(3) for y in range(3)), 9, 9)
    but = ("emboite", ((20, 20),), (11, 14), (((20, 20), 11),))
    assert not Theorie._vrai(but, (piece,)) and Theorie._vrai(but, (bloc,))
    assert Theorie._vrai(but[:3], (piece,))
