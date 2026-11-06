from types import SimpleNamespace
import numpy as np
import pytest
from exploration_p1_prefixe import GrapheIntegral,charger_observations,proposer


def test_episodes_ne_creent_pas_transition_reset_et_evitent_repetition():
    g=np.zeros((8,8),dtype=int);h=g.copy();h[3,3]=2
    ep={'grilles':[g,h],'actions':[1],'issues':['continue']}
    ex=GrapheIntegral(SimpleNamespace(image=g,actions_disponibles=[1,2]),None)
    n,amb=charger_observations(ex,[ep,{'grilles':[g],'actions':[],'issues':[]}])
    assert n==1 and not amb
    assert ex.aretes=={ex.cle(g):{1:ex.cle(h)}}
    assert proposer([g],[],[],[1,2],observations_episodes=[ep])['actions']==[2]


def test_contradiction_ne_remplace_pas_ancienne_arete_par_derniere():
    g=np.zeros((8,8),dtype=int);h=g.copy();h[3,3]=2
    ex=GrapheIntegral(SimpleNamespace(image=g,actions_disponibles=[1,2]),None)
    ep=lambda finale:dict(grilles=[g,finale],actions=[1],issues=['continue'])
    n,amb=charger_observations(ex,[ep(h),ep(g),ep(h)])
    assert n==3 and amb=={(ex.cle(g),1)}
    assert 1 not in ex.aretes[ex.cle(g)]
    with pytest.raises(ValueError,match='RESET'):
        charger_observations(ex,[dict(grilles=[g,g],actions=[0],issues=['continue'])])
