from pathlib import Path
from avancer_agent_relais import charger_agent
from mouvement_relatif_film import verifier

P=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n3_heritage29/agent.pkl'

def rapport(coup):
    a=charger_agent(P);h=a.hypotheses_capacites_heritees[0]['hypothese']
    return verifier(a.images[coup-1],a.films[coup-1],h['support_motif_stable'],h['forme'],
        [{'support':[35,11],'independante':[36,12]}])

def test_film29_verifie_relative_malgre_prediction_ecran_fausse():
    r=rapport(29);a=r['associations'][0]
    assert r['images']==8 and a['relation_relative_verifiee']
    assert a['supports'][-1]==[33,11]
    assert not a['contenance_certifiee'] and not r['but_certifie']

def test_film28_immobile_ne_valide_pas_transport():
    r=rapport(28)
    assert not r['associations'][0]['relation_relative_verifiee']

def test_association_heritee_revalidee_alimente_transport_existant():
    from revalidation_capacites_heritees import proposer
    from transport_relationnel import proposer as transport
    a=charger_agent(P)
    assert proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic) is None
    assert a.memoire_mouvement_conjoint['association_relative_film']['associations'][0]['relation_relative_verifiee']
    d=transport(a,[1,2,3,4,6,7])
    assert d['actions']==[4] and d['origine']=='transport_vers_frontiere_relation'
    assert d['votes_frontiere']==[28,36]
    assert not d['contrat_prediction_partielle']['but_certifie']
