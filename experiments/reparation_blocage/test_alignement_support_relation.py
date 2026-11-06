from pathlib import Path
from avancer_agent_relais import charger_agent
from alignement_support_relation import proposer

P=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n3_contexte47/agent.pkl'

def test_bfs_reutilise_quatre_directions_apprises_et_trou_explicite():
    a=charger_agent(P);d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert d['actions']==[1]
    assert d['route_acces_hypothetique']==[1,1,4,4,2,2,4]
    assert d['suivi']['images_non_resolues']==[32]
    assert d['associations_candidates']==[{'piste':0,'route':[1,1,4,4,2,2,4]}]
    assert not d['contrat_prediction_partielle']['but_certifie']

def test_transport_reutilise_suivi_partiel_apres_prise_56():
    from transport_relationnel import proposer as transport
    p=P.parent.parent/'lf52_n3_alignement48/agent.pkl';a=charger_agent(p)
    d=transport(a,[1,2,3,4,6,7])
    assert d['actions']==[3] and d['route_acces_hypothetique']==[3,1,1,3,3,2,2,3,3]
    assert d['contrat_prediction_partielle']['forme_candidate']==[30,48]

def test_transport_propose_orientation_inverse_apres_selection_non_confirmee():
    from relation_clic_observee import proposer_agent
    a=charger_agent(P.parent.parent/'lf52_n3_transport57/agent.pkl')
    d=proposer_agent(a,[1,2,3,4,6,7])
    assert d['source']==(30,48) and d['voisin']==(24,48)
    assert d['destination_candidate']==(18,48)
    assert not a.memoire_relation_clic['refutee']
