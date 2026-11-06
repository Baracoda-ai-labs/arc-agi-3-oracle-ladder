from types import SimpleNamespace
import numpy as np
from revalidation_capacites_heritees import question_deja_observee

def test_masque_question_persiste_sans_effacer_contexte():
    a=np.zeros((4,4),dtype=int);b=a.copy();b[0,0]=1
    agent=SimpleNamespace(images=[a,b],actions=[1],revalidations_capacites=[{'index':0,'masque_priorite_heuristique':[[0,0]]}])
    assert question_deja_observee(agent,1,set())
    assert not question_deja_observee(agent,2,set())
    b[2,2]=3
    assert not question_deja_observee(agent,1,set())
    assert a[0,0]==0 and b[0,0]==1

def test_prefixe_82_ne_repropose_pas_question_80():
    from pathlib import Path
    from avancer_agent_relais import charger_agent
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_commun81/agent.pkl'
    a=charger_agent(p);a.images=a.images[:83];a.actions=a.actions[:82]
    a.revalidations_capacites=[v for v in a.revalidations_capacites if v['coup']<=82]
    assert question_deja_observee(a,1,set())
