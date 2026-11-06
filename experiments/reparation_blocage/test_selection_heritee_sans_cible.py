from pathlib import Path
from avancer_agent_relais import charger_agent
from selection_heritee_sans_cible import proposer

P=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_commun1/agent.pkl'

def test_selection_connue_sans_exiger_partenaire_reconnu():
    a=charger_agent(P);d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert d['actions']==[['clic',13,25]]
    assert 'partenaire' in d['abstentions'] and not d['modeles']
    assert a.selection_heritee_en_attente['source']=='affordance_selection_anterieure'

def test_pas_de_clic_sans_action_offerte():
    a=charger_agent(P)
    assert proposer(a,[1,2,3,4,7],a.memoire_relation_clic) is None
