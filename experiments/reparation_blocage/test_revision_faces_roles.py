import copy
from pathlib import Path
import cloudpickle,numpy as np,pytest
from chaine_coherente import Chaine
from chaine_agent_integree import lots,canon
from revision_faces_contact import proposer

@pytest.fixture
def source():
    root=Path(__file__).parent/'runs'
    a=cloudpickle.loads((root/'ka59_transfert_roles_n2_1/agent.pkl').read_bytes())
    b=cloudpickle.loads((root/'ka59_n2_portefeuille32_1/agent.pkl').read_bytes())
    c=a.chaines['transfert_roles']
    source=Chaine(c.perception,c.programme,[g.tolist() for g in b.images],lots(b.actions),[],films=b.films)
    return source,a,b

def test_orientation_nouvelle_rejoue35_sans_modifier_lois(source):
    s,a,b=source
    programme=copy.deepcopy(s.programme);m=s.perception
    c,d=proposer(s)
    assert d['admis'] and d['orientation']==[-3,0] and d['pixels_observes']==6
    assert d['controle']['transitions']==35 and d['controle']['compilation_fidele']
    assert c.programme['regles'][:-1]==programme['regles']
    assert c.programme['regles'][-1]['nom']=='face_contact_-3_0'
    assert s.programme==programme and m.source.faces==[(3,0,[(0,2),(1,2),(2,2)],0)]
    assert {f[:2] for f in c.perception.source.faces}=={(3,0),(-3,0)}
    assert all('face_3_0' in p['attrs'] and 'face_-3_0' in p['attrs'] for p in c.perception.pieces)
    _,(pc,sc)=c.rejouer()
    assert np.array_equal(c.perception.rendu(sc),c.perception.vue(b.images[-1]))

def test_ecart_hors_face_refuse(source):
    s,_,_=source;s.grilles[-1][10][10]=0
    c,d=proposer(s)
    assert c is None and d['refus']=='pas_de_face_adjacente_etayee'

def test_observer_raccord_meme_avec_clics(source):
    s,a,b=source
    for k in range(32,35):
        c=a.chaines['transfert_roles'];act=b.actions[k]
        c.plan={'actions':[canon(act)],**c.signature(),'origine':'experience_test'};c._tracer_plan()
        a.attente={'actions':[act],'modeles':['transfert_roles']}
        a.observer(act,b.images[k+1],b.films[k],'continue',source='trace')
    assert 'transfert_roles/face_contact' in a.chaines
    assert a.chaines['transfert_roles/face_contact'].rejouer()[0]['transitions']==35
