import copy,json
from pathlib import Path
import cloudpickle,numpy as np,pytest
from chaine_coherente import Chaine
from chaine_agent_integree import lots,canon
from revision_faces_contact import proposer as face
from glissade_distance_observee import proposer,compiler,apprendre
from transfert_roles import RolesReaffectes,parametrer
R=Path(__file__).parent/'runs'

@pytest.fixture
def donnees():
    a=cloudpickle.loads((R/'ka59_transfert_roles_n2_1/agent.pkl').read_bytes());s=a.chaines['transfert_roles']
    z=np.load(R/'relais_ka59_contact1/N2/partie.npz');g=z['images'][:37]
    actions=json.loads((R/'relais_ka59_contact1/N2/partie.json').read_text())['actions'][:36]
    films=[z[f'film_{i}'] for i in range(1,37)]
    c=Chaine(s.perception,s.programme,g[:36].tolist(),lots(actions[:35]),[],films=films[:35]);c,d=face(c);assert d['admis']
    c=Chaine(c.perception,c.programme,g.tolist(),lots(actions),[],films=films)
    return c,a,g,actions,films

def test_distance_source_n1_et_validation36(donnees):
    source,a,g,actions,films=donnees
    avant=copy.deepcopy(source.programme)
    c,d=proposer(source,a.precedents)
    assert d['admis'] and d['distance']==15 and d['controle']['transitions']==36
    assert d['validations_precedents'][0]['controle']['transitions']==80
    assert d['validations_precedents'][0]['finale_confirmee']
    assert source.programme==avant
    noms={r['nom']:r for r in c.programme['regles']}
    for r in avant['regles']:
        if not r['nom'].startswith('mouvement_'):assert noms[r['nom']]==r
    _,(pc,sc)=c.rejouer()
    assert np.array_equal(c.perception.rendu(sc),c.perception.vue(g[-1]))
    assert any(p['x']==18 and p['y']==42 for p in sc.sprites if 'piece' in p.get('tags',[]))

def test_archive_ancienne_n1_25_heldout(donnees):
    source,a,*_=donnees
    classe,glisse,preuves=apprendre(source.perception,a.precedents)
    z=np.load(R/'recherche_briques_ka59_1/N1/partie.npz');g=z['images'];actions=json.loads((R/'recherche_briques_ka59_1/N1/partie.json').read_text())['actions']
    prototype=source.perception.source;v=RolesReaffectes(prototype,g[0]);p=compiler(v,parametrer(prototype,prototype.programme()),classe,glisse);v.programme_transfere=p
    c=Chaine(v,p,g[:-1].tolist(),lots(actions[:-1]),[],films=[z[f'film_{i}'] for i in range(1,len(actions))])
    check,cur=c.rejouer();assert cur and check['transitions']==24
    cur[0].step(cur[1],canon(actions[-1]));assert cur[1].issue=='niveau'

def test_precedent_contredit_refuse(donnees):
    source,a,*_=donnees;h=copy.deepcopy(a.precedents);h[0]['grilles'][1][10][10]=0
    c,d=proposer(source,h)
    assert c is None and d['refus']=='precedent_refute'

def test_pas_de_film_pas_de_distance(donnees):
    source,a,*_=donnees;h=copy.deepcopy(a.precedents);h[0]['films']=[]
    c,d=proposer(source,h)
    assert c is None and 'filmée' in d['refus']

def test_observer_revision_distance(donnees):
    source,a,g,actions,films=donnees
    for k in range(32,36):
        name=next(iter(a.chaines));c=a.chaines[name]
        c.plan={'actions':[canon(actions[k])],**c.signature(),'origine':'test'};c._tracer_plan()
        a.attente={'actions':[actions[k]],'modeles':[name]}
        a.observer(actions[k],g[k+1],films[k],'continue',source='trace')
    assert any(n.endswith('/distance_glissade') for n in a.chaines)
    assert next(iter(a.chaines.values())).rejouer()[0]['transitions']==36
