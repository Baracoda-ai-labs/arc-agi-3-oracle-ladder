from pathlib import Path
import copy
import numpy as np
from avancer_agent_relais import charger_agent
from revalidation_capacites_heritees import proposer

SOURCE=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n3_commun9/agent.pkl'

def test_archive_24_choisit_alignement_sans_activer_transport():
    a=charger_agent(SOURCE); avant=copy.deepcopy(a.hypotheses_capacites_heritees)
    d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert d['actions']==[3]
    assert d['contrat_hypotheses']['supports']==[[29,47],[35,11]]
    assert d['contrat_hypotheses']['phase']=='alignement_relation'
    assert d['contrat_hypotheses']['episode_source_sha256']
    assert a.hypotheses_capacites_heritees==avant
    assert not getattr(a,'memoire_mouvement_conjoint',None)

def test_blocage_ne_confirme_pas_transport():
    a=charger_agent(SOURCE); proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    a.actions.append(3);a.images.append(a.images[-1].copy());a.issues.append('continue')
    proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert a.revalidations_capacites[-1]['supports_exacts'] is False
    assert not getattr(a,'memoire_mouvement_conjoint',None)

def test_sans_heritage_pas_de_nouvelle_hypothese():
    a=charger_agent(SOURCE);a.hypotheses_capacites_heritees=[]
    assert proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic) is None

def test_blocage_28_avec_compteur_ne_rejoue_pas_question():
    a=charger_agent(SOURCE.parent.parent/'lf52_n3_heritage25/agent.pkl')
    d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert a.revalidations_capacites[-1]['discrimination_valide'] is False
    assert d['actions']==[4]
    assert not getattr(a,'memoire_mouvement_conjoint',None)
