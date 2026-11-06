from pathlib import Path
from avancer_agent_relais import charger_agent
from revalidation_capacites_heritees import proposer
from relation_clic_observee import proposer_agent

SOURCE=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_selection66/agent.pkl'

def test_capacite_active_ne_masque_pas_commande_heritee_hors_segment():
    a=charger_agent(SOURCE)
    assert a.memoire_mouvement_conjoint.get('association_relative_film')
    d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert d['actions']==[3]
    assert d['contrat_hypotheses']['phase']=='mouvement_conjoint'
    assert d['contrat_hypotheses']['episode_source_sha256']
    assert d['risque']=='inconnu' and d['but']=='inconnu'

def test_raccord_commun_choisit_experience_horizontale_pas_selection_repetee():
    a=charger_agent(SOURCE)
    d=proposer_agent(a,[1,2,3,4,6,7])
    assert d['actions']==[3] and d['origine']=='revalidation_capacite_heritee'
