import numpy as np
import pytest
from chaine_coherente import Chaine
from roles_observes import PerceptionRoles

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import NOMS


@pytest.mark.parametrize('couleurs,offset',[([9,1,2,7],0),([0,8,6,3],7),([5,12,11,4],12)])
def test_revele_sol_et_roles_sans_couleur_position_fixe(couleurs,offset):
    fond,sol,mobile,cible=couleurs
    def image(x,y):
        g=np.full((64,64),fond,dtype=np.int16)
        g[6+offset:30+offset,6+offset:30+offset]=sol
        g[25+offset:28+offset,25+offset:28+offset]=cible
        g[y+offset:y+offset+3,x+offset:x+offset+3]=mobile
        return g
    gs=[image(12,12),image(15,12),image(12,12),image(12,15),image(12,12)]
    actions=[4,3,2,1];v=PerceptionRoles(gs,actions)
    p=v.programme(v.buts[0]);c=Chaine(v,p,[g.tolist() for g in gs],
        [{'actions':[{'action':NOMS[a]}]} for a in actions],[(NOMS[a],) for a in actions])
    assert c.rejouer()[1] is not None
    assert len(v.preuves_decor)==9 and v.franchis
    sc=v.scene(gs[0]);pc=Programme(p)
    pc.step(sc,('RIGHT',));pc.step(sc,('RIGHT',))
    assert np.array_equal(v.rendu(sc),v.vue(image(18,12)))
