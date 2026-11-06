from pathlib import Path
from avancer_agent_relais import charger_agent
import transport_relationnel as tr
SOURCE=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_commun18/agent.pkl'

def test_desaccord_conduit_experience_et_non_plan_sur():
    a=charger_agent(SOURCE);d=tr.proposer(a,[1,2,3,4,6,7])
    assert d['actions']==[4]
    assert d['garde_navigation']=='desaccord_entre_gardes_candidates_experience_un_pas'
    oui,n=d['votes_premier_pas'];assert 0<oui<=n
    assert d['risque']=='inconnu' and not d['contrat_prediction_partielle']['but_certifie']
    assert len(d['actions'])==1

def test_refus_unanime_ne_devient_pas_route(monkeypatch):
    original=tr.apprendre
    def refus(*args,**kwargs):
        g,m,p=original(*args,**kwargs)
        return [dict(x,permis=[]) for x in g],m,p
    monkeypatch.setattr(tr,'apprendre',refus)
    assert tr.proposer(charger_agent(SOURCE),[1,2,3,4,6,7]) is None
