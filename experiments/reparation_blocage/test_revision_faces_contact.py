import copy,json
from pathlib import Path
import numpy as np
import pytest
from roles_observes import PerceptionRoles
from chaine_coherente import Chaine
from chaine_agent_integree import AgentIntegre,lots,canon
from revision_faces_contact import proposer
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.plan_langage import cle_complete

@pytest.fixture
def contact():
    r=Path(__file__).parent/'runs/ka59_anti_cycles1/N1'
    z=np.load(r/'partie.npz');g=z['images'];a=json.loads((r/'partie.json').read_text())['actions']
    films=[z[f'film_{i}'].tolist() for i in range(1,73)]
    m=PerceptionRoles(g[:46],a[:45])
    c=Chaine(m,m.programme(m.buts[1]),g[:47].tolist(),lots(a[:46]),[],films=films[:46])
    return c,g,a,films

def test_prefixe46_et_suffixe_independant(contact):
    source,g,a,films=contact;original=copy.deepcopy(source.programme)
    c,d=proposer(source)
    assert d['admis'] and d['controle']['transitions']==46
    assert all(isinstance(x,int) for x in a[:46])
    assert source.programme==original
    assert c.programme['regles'][:len(original['regles'])]==original['regles']
    assert c.perception.signature_observation()==source.perception.signature_observation()
    _,(pc,sc)=c.rejouer();pi=Programme(c.programme);pi.etat=copy.deepcopy(pc.etat);si=copy.deepcopy(sc)
    erreurs=[]
    for i in range(46,72):
        pc.step(sc,canon(a[i]));pi.step(si,canon(a[i]))
        assert cle_complete(sc,pc.etat)==cle_complete(si,pi.etat)
        erreurs.append(int((c.perception.rendu(sc)!=c.perception.vue(g[i+1])).sum()))
    assert erreurs[0]==21  # Dynamique encore inconnue, pas validation du suffixe.
    assert len(c.grilles)==47 and len(erreurs)==26
    with pytest.raises(ValueError,match='Appariement'):
        c.perception.scene(g[46])  # Limite explicite : seul état rejoué est utilisable.

def test_changement_hors_face_refuse(contact):
    source,g,a,films=contact;source.grilles[-1][35][35]=0
    c,d=proposer(source)
    assert c is None and d['refus']=='pas_de_face_adjacente_etayee'

def test_prefixe_contradictoire_refuse(contact):
    source,g,a,films=contact;source.grilles[40][35][35]=0
    c,d=proposer(source)
    assert c is None and d['refus']=='prefixe_deja_refute'

def test_observer_raccord_contact_meme_avec_clic_anterieur(contact):
    source,g,a,films=contact
    c=Chaine(source.perception,source.programme,g[:46].tolist(),lots(a[:45]),[],films=films[:45])
    c.activer_atms();c.plan={'actions':[canon(a[45])],**c.signature(),'origine':'experience_test'};c._tracer_plan()
    agent=AgentIntegre(g[:46],a[:45],films[:45],['continue']*45)
    agent.actions[0]=['clic',0,0]  # Garde globale seulement ; historique c reste indépendant.
    agent.chaines={'roles':c};agent.attente={'actions':[a[45]],'modeles':['roles']}
    agent.observer(a[45],g[46],films[45],'continue',source='trace')
    assert 'roles/face_contact' in agent.chaines
