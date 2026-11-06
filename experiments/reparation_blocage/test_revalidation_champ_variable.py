from pathlib import Path
import copy
from avancer_agent_relais import charger_agent
from revalidation_capacites_heritees import proposer

SOURCE=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_commun13/agent.pkl'

def test_commandes_avant_entree_dans_champ_reutilisees_sans_identite_inventee():
    a=charger_agent(SOURCE)
    heritage=copy.deepcopy(a.hypotheses_capacites_heritees)
    d=proposer(a,[1,2,3,4,6,7],a.memoire_relation_clic)
    assert d['origine']=='revalidation_capacite_heritee'
    assert d['actions']==[3]
    assert d['contrat_hypotheses']['phase']=='mouvement_conjoint'
    assert d['contrat_hypotheses']['supports']==[[11,23]]
    assert d['contrat_hypotheses']['autres_supports']=='inconnus'
    assert not d['activation_transport']
    assert not getattr(a,'memoire_mouvement_conjoint',None)
    assert a.hypotheses_capacites_heritees==heritage


def test_decision_commune_ne_confond_pas_refutation_clic_et_transport(monkeypatch):
    monkeypatch.setattr("diagnostic_champ_commun.reexaminer",lambda *args:False)
    a=charger_agent(SOURCE)
    a.recherche_prolongee=False
    d=a.decider([1,2,3,4,6,7],secondes=1)
    assert a.memoire_relation_clic['refutee']
    assert d['origine']=='revalidation_capacite_heritee'
    assert d['actions']==[3]
    assert d['contrat_hypotheses']['phase']=='mouvement_conjoint'
    assert not getattr(a,'memoire_mouvement_conjoint',None)
