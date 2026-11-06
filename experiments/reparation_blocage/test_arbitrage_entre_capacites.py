from pathlib import Path
from avancer_agent_relais import charger_agent
from relation_clic_observee import proposer_agent

def test_selection_observable_prioritaire_sur_navigation_repetee(monkeypatch):
    monkeypatch.setattr("arbitre_capacites_partielles.proposer_navigation",lambda *args:{"actions":[2],"preuve":{"repetitions_position_action":3}})
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_priorite62/agent.pkl')
    d=proposer_agent(a,[1,2,3,4,6,7])
    assert d['origine']=='selection_heritee_sans_cible'
    assert d['priorite']=='changer_capacite_avant_repetition_navigation'
    assert d['actions']==[['clic',40,19]]
    assert d['but']=='inconnu'


def test_prefixe65_selection_accessible_sans_forcer_navigation():
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_priorite62/agent.pkl')
    d=proposer_agent(a,[1,2,3,4,6,7])
    assert d['origine']=='selection_heritee_sans_cible' and d['actions']==[['clic',40,19]]
