import numpy as np
from objets_variables import ObjetsVariables
from perception_guidee import proposer_calques

from chrysalide.arc3.moteur import NOMS


def test_contact_conserve_hypotheses_et_ne_masque_pas_les_erreurs():
    def image(x, y):
        g = np.ones((64, 64), dtype=np.int16)
        g[24:30, 24:30] = 8
        g[y:y+6, x:x+6] = 2
        for yy in (25, 28):
            for xx in (25, 28):
                g[yy, xx] = 8
        return g
    actions = [4, 2, 3, 1] + [2]*6 + [4]*5
    x, y = 6, 6
    gs = [image(x, y)]
    for a in actions:
        dx, dy = {1: (0, -3), 2: (0, 3), 3: (-3, 0), 4: (3, 0)}[a]
        x, y = x+dx, y+dy
        gs.append(image(x, y))
    v = ObjetsVariables(gs[:5], actions[:4])
    p = v.programme(v.buts[0])
    noms = [(NOMS[a],) for a in actions]
    cs, d = proposer_calques(v, p, [g.tolist() for g in gs], noms)
    assert {n for n, _ in cs} == {'detail_local', 'detail_periodique'}
    assert all(c.rejouer()[1] is not None for _, c in cs)
    assert d['pixels_ecart'] == [(25, 25), (28, 25)]
    for _, c in cs:
        assert np.array_equal(c.perception.vue(gs[-1]), v.vue(gs[-1]))
    faux = [g.copy() for g in gs]
    faux[-1][10, 40] = 9
    assert proposer_calques(v, p, [g.tolist() for g in faux], noms)[0] == []
