from pathlib import Path
from avancer_agent_relais import charger_agent
from revalidation_capacites_heritees import proposer
from masque_priorite_contextuelle import cellules_priorite
import copy

BASE=Path(__file__).parent/'runs/stream_multijeux_26_10'

def test_commande_partielle_et_compteur_ne_bloquent_pas_les_acquis():
    a=charger_agent(BASE/'lf52_n4_commun72/agent.pkl');avant=a.images[-1].copy()
    d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    c=d['contrat_hypotheses']
    assert d['actions']==[1] and c['supports']==[[38,11]]
    assert c['portee_supports']=='porteurs_seulement' and c['autres_supports']=='inconnus'
    assert len(cellules_priorite(a.images))==64 and (a.images[-1]==avant).all()
    assert not c['but_certifie']

def test_autre_support_immobile_ne_refute_pas_une_prediction_partielle():
    a=charger_agent(BASE/'lf52_n4_approche31/agent.pkl')
    a.actions=a.actions[:21];a.images=a.images[:22];a.films=a.films[:21];a.issues=a.issues[:21]
    h=a.hypotheses_capacites_heritees[0]
    a.revalidation_capacite_attente={'index':20,'phase':'alignement_relation','motif':h['hypothese']['support_motif_stable'],
        'supports':[[23,53]],'portee_supports':'porteurs_seulement','associations':[],
        'episode_source_sha256':h['episode_source_sha256'],'palette_mobile':[11,12,14]}
    proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert a.revalidations_capacites[-1]['coup']==21
    assert a.revalidations_capacites[-1]['supports_exacts']

def test_refus_contextuel_deja_observe_ne_recommence_pas_avec_compteur_seul():
    a=charger_agent(BASE/'lf52_n4_commun72/agent.pkl')
    assert proposer(a,[3],a.memoire_relation_clic) is None
