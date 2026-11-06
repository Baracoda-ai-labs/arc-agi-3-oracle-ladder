import numpy as np
import garde_support_navigation as nav
from pathlib import Path
from avancer_agent_relais import charger_agent
from alignement_support_relation import proposer

def test_inconnu_distinct_de_blocage_observe(monkeypatch):
    monkeypatch.setattr(nav,'apprendre',lambda *args:([{'offset':[0,0],'permis':[1],'bloques_observes':[0]}],{4:(1,0)},[(0,0)]))
    d=nav.proposer([np.array([[2,9,9]])],[],np.array([[2]]),[4],cibles={(1,0)})
    assert d['actions']==[4] and d['portee_garde']=='valeurs_non_observees_hypothese'
    assert nav.proposer([np.array([[2,0,9]])],[],np.array([[2]]),[4],cibles={(1,0)}) is None
    assert nav.proposer([np.array([[2,-1,9]])],[],np.array([[2]]),[4],cibles={(1,0)}) is None

def test_archive_forme_isolee_devient_cible_de_relation_sans_transport_certifie():
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_relation27/agent.pkl')
    d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert d['actions']==[1] and d['contrat_prediction_partielle']['piste']==1
    assert d['portee_garde']=='valeurs_non_observees_hypothese'
    assert not d['contrat_prediction_partielle']['but_certifie']
