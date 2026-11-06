from pathlib import Path
from avancer_agent_relais import charger_agent
from passage_clic_observe import apprendre
from relation_clic_observee import proposer_agent

P=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_selection11/agent.pkl'

def test_apprend_deplacement_avec_population_et_motif_conserves():
    a=charger_agent(P);ps=apprendre(a,a.memoire_relation_clic['forme'])
    assert len(ps)==1 and ps[0]['coup']==10
    assert ps[0]['source']==[12,24] and ps[0]['destination']==[24,24]
    assert ps[0]['population_forme_conservee'] and not ps[0]['but_certifie']

def test_hypothese_prospective_choisit_destination_non_revisitee():
    a=charger_agent(P);d=proposer_agent(a,[1,2,3,4,6,7])
    assert d['origine']=='passage_clic_hypothese_transferee'
    assert d['contrat_prediction_partielle']['sources']==[[24,24]]
    assert d['contrat_prediction_partielle']['destination']==[36,24]
    assert d['preuve_source']['coup']==10
    assert not a.memoire_relation_clic['refutee']
