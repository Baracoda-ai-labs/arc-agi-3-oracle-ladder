from pathlib import Path
import cloudpickle,copy
from revision_but_roles import couverture
from buts_roles_herites import candidats

R=Path(__file__).parent/'runs/ka59_n3_glissade_classe28_candidate1'
def test_calque_revele_pas_nouvelle_cible_et_prior_classe_mobile():
    c=cloudpickle.loads((R/'candidat.pkl').read_bytes());a=cloudpickle.loads((R/'agent_observe28.pkl').read_bytes())
    p=copy.deepcopy(c.programme)
    hyp=couverture(c.perception)
    assert all(len(h['centres'])==2 for h in hyp)
    cs,d=candidats(a,c)
    assert cs and cs[0][0]['role_mobile_observe']
    assert d['prior_source']=='preuve_revision_but' and d['precedents_disponibles']==2
    assert any(n=='pousse_cibles' for n,_ in d['classification_hypothetique'])
    for desc,new in cs:
        assert not desc['but_confirme']
        assert new.programme['regles'][:-1]==p['regles']
        ctrl,state=new.rejouer();assert state and ctrl['transitions']==28
        assert new.programme['regles'][-1]['quand'][1]==c.preuve_revision_but['but_refute']['quand']
    assert c.programme==p

def test_absence_prior_ne_fabrique_pas_un_but():
    c=cloudpickle.loads((R/'candidat.pkl').read_bytes());a=cloudpickle.loads((R/'agent_observe28.pkl').read_bytes())
    del c.preuve_revision_but;a.modeles_but_refute={}
    assert candidats(a,c)[0]==[]


def test_admission_garde_dynamique_et_ne_readmet_pas_but_refute():
    from buts_roles_herites import admettre
    c=cloudpickle.loads((R/'candidat.pkl').read_bytes())
    a=cloudpickle.loads((R/'agent_observe28.pkl').read_bytes())
    a.chaines={'perception_sans_but_test':c}
    assert admettre(a,2)
    noms=[n for n in a.chaines if n.startswith('but_roles_herite/')]
    assert noms and a.chaines['perception_sans_but_test'] is c
    rejete=noms[0];a.modeles_but_refute[rejete]=a.chaines.pop(rejete)
    a.buts_roles_deja_proposes=set()
    admettre(a,2)
    assert rejete not in a.chaines
    assert not admettre(a,2)
