# SPDX-License-Identifier: MIT-0
"""verifier_loi (CCM-102-B) : une loi juste explique plus de transitions, une loi fausse en perd."""
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.logique.verifier import verifier_loi


class Tr:
    def __init__(self, etats, actions, taille=(6, 1)):
        self.etats, self.actions, self.taille, self.exclues = etats, actions, taille, frozenset()


F = frozenset({(0, 0)})


def _tr():
    # mobile 1 va à droite (action 4) de x=0 à x=3
    return Tr([((1, F, x, 0),) for x in range(4)], [4, 4, 4])


def test_loi_juste_acceptee():
    r = verifier_loi(Theorie(), ("move", 1, 4, 1, 0), [_tr()])
    assert r["avant"] == (0, 3) and r["apres"] == (3, 3) and r["accepte"]


def test_loi_fausse_refusee():
    th = Theorie(moves={(1, 4): (1, 0)})
    r = verifier_loi(th, ("move", 1, 4, 2, 0), [_tr()])
    assert r["apres"][0] < r["avant"][0] and not r["accepte"] and r["perdues"]
