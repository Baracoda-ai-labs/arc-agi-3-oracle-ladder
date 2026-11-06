import copy
from pathlib import Path
import cloudpickle
from revision_glissade_classe import proposer

R=Path(__file__).parent/'runs/ka59_n3_glissade_classe28_candidate1'
def fixture():
    return cloudpickle.loads((R/'source28.pkl').read_bytes()),cloudpickle.loads((R/'agent_observe28.pkl').read_bytes())

def test_prefixe28_classe_passive_sans_selection_ni_nouvelle_distance():
    s,a=fixture();avant=copy.deepcopy(s.programme)
    c,d=proposer(s,a.precedents)
    assert c and d['controle']['transitions']==28 and d['controle']['compilation_fidele']
    assert d['distance_heritee']==15 and d['sol_revele_pixels']==45
    assert c.but_inconnu and c.preuve_revision_but==s.preuve_revision_but
    assert s.programme==avant
    noms={r['nom'] for r in c.programme['regles'] if r['nom'].startswith('glissade')}
    assert [r for r in c.programme['regles'] if r['nom'] not in noms]==[r for r in avant['regles'] if r['nom'] not in noms]
    _,(_,sc)=c.rejouer()
    assert len([o for o in sc.sprites if 'piece' in o.get('tags',[])])==1
    assert any(o['x']==20 and o['y']==20 and 'bloqueur' in o.get('tags',[]) for o in sc.sprites)
    assert any(o['x']==50 and o['y']==20 and 'bloqueur' in o.get('tags',[]) for o in sc.sprites)

def test_pas_de_film_pas_de_promotion():
    s,a=fixture();s.films.entrees[-1]=None
    assert proposer(s,a.precedents)[0] is None

def test_distance_heritee_alteree_refusee():
    s,a=fixture()
    next(r for r in s.programme['regles'] if r['nom'].startswith('glissade c'))['quand']=False
    c,d=proposer(s,a.precedents)
    assert c is None and d['refus']=='glissade_heritee_non_identique'
