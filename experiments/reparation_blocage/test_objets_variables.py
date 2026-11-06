import numpy as np
import pytest
from chaine_coherente import Chaine
from objets_variables import ObjetsVariables

from chrysalide.arc3.moteur import NOMS


@pytest.mark.parametrize('n', [1, 3, 5])
def test_cardinalite_variable_sans_victoire(n):
    def image(dx, dy):
        g = np.ones((64, 64), dtype=np.int16)
        g[45:47, 40:42] = 14
        for i in range(n):
            k = 2+i
            g[8+dy:8+dy+k, 4+10*i+dx:4+10*i+dx+k] = 2+i
        return g
    gs = [image(0, 0), image(1, 0), image(1, 1), image(0, 1), image(0, 0)]
    actions = [4, 2, 3, 1]
    v = ObjetsVariables(gs, actions)
    assert len(v.mobiles) == n
    assert v.buts
    c = Chaine(v, v.programme(v.buts[0]), [g.tolist() for g in gs],
               [{'actions': [{'action': NOMS[a]}]} for a in actions], [(NOMS[a],) for a in actions])
    controle, etat = c.rejouer()
    assert etat is not None and controle['compilation_fidele']


def test_appariement_refuse_doublon():
    from objets_variables import localiser
    with pytest.raises(ValueError, match='unique'):
        localiser(np.ones((4, 4)), np.ones((2, 2)))


def test_piece_multicolore_contact_comme_candidat():
    def image(d):
        a = np.ones((64, 64), dtype=np.int16)
        a[10:15, 10+d:15+d] = 2
        a[12, 12+d] = 3
        a[40:45, 40:45] = 8
        return a
    gs = [image(0), image(1), image(0), image(1)]
    v = ObjetsVariables(gs, [4, 3, 4], contact=True)
    assert len(v.mobiles) == 1
    assert set(np.unique(v.mobiles[0])) == {2, 3}
    c = Chaine(v, v.programme(v.buts[0]), [g.tolist() for g in gs],
               [{'actions': [{'action': NOMS[a]}]} for a in [4, 3, 4]], [('LEFT',), ('RIGHT',)])
    assert c.rejouer()[1] is not None
