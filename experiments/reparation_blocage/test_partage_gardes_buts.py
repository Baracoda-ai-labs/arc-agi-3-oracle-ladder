import copy,cloudpickle
from pathlib import Path
from types import SimpleNamespace
from revision_garde_face import partager_gardes
from revision_faces_contact import proposer
from buts_roles_herites import admettre,signature_semantique
from chaine_coherente import Chaine
R=Path(__file__).parent/'runs'

def test_faces_partagent_garde_et_rejouent_53():
    s=cloudpickle.loads((R/'ka59_n3_garde_face52_auto1/source52_refute.pkl').read_bytes())
    from revision_garde_face import proposer as reviser
    c,d=reviser(s)
    # L'exclusion est partagée aux orientations déjà apprises, sans mutation source.
    assert partager_gardes(c.programme)==c.programme
    assert c.programme!=s.programme
    assert c.rejouer()[0]['transitions']==52

def test_dedup_ignore_nom_mais_pas_dynamique_ni_perception():
    a=cloudpickle.loads((R/'ka59_n3_roles_buts45_auto1/agent.pkl').read_bytes())
    c=a.chaines['but_roles_herite/45a7d33b9aee2b17'];d=copy.deepcopy(c)
    a.chaines={'ancien/repare':c,'nouveau':d}
    assert not admettre(a,0) and list(a.chaines)==['ancien/repare']
    d.programme['etat']['hypothese_test']=False
    assert signature_semantique(d)!=signature_semantique(c)
    d=copy.deepcopy(c);d.perception.statiques[-1]['couche']=-9
    assert signature_semantique(d)!=signature_semantique(c)

def test_admission_ne_recree_pas_but_sous_nom_repare():
    a=cloudpickle.loads((R/'ka59_n3_roles_buts45_auto1/agent.pkl').read_bytes())
    a.chaines={n+'/repare':c for n,c in a.chaines.items()}
    avant=len(a.chaines);a.buts_roles_deja_proposes=set()
    assert not admettre(a,2) and len(a.chaines)==avant
