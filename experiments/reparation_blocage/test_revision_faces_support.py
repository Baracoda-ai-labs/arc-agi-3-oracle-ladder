import copy
from pathlib import Path
import cloudpickle
from chaine_coherente import Chaine
from chaine_agent_integree import lots
from revision_faces_contact import proposer,regle_face_support

R=Path(__file__).parent/'runs'
def source():
    avant=cloudpickle.loads((R/'ka59_n3_experience_contact21_23_1/agent.pkl').read_bytes())
    apres=cloudpickle.loads((R/'ka59_n3_face_support27_candidate1/source27.pkl').read_bytes())
    c=next(iter(avant.chaines.values()))
    s=Chaine(c.perception,c.programme,[g.tolist() for g in apres.images],lots(apres.actions),c.actions,coups_deja_joues=len(apres.actions),reserve=c.limite,films=apres.films)
    s.but_inconnu=True;s.preuve_revision_but=copy.deepcopy(c.preuve_revision_but)
    return s

def test_prefixe27_face_orthogonale_et_dynamique_conservee():
    s=source();p=copy.deepcopy(s.programme);v=s.perception.signature_observation()
    c,d=proposer(s)
    assert c is not None,d
    assert d['orientation']==[0,-3] and d['voisin_tag']=='bloqueur' and d['pixels_observes']==3
    assert d['controle']['transitions']==27 and d['controle']['compilation_fidele']
    assert c.programme['regles'][:-1]==p['regles'] and c.programme['regles'][-1]['nom']=='face_support_bloqueur_0_-3'
    assert s.programme==p and c.perception.signature_observation()==v
    assert c.but_inconnu and c.preuve_revision_but==s.preuve_revision_but

def test_support_transparent_ne_declenche_pas_la_face():
    from chrysalide.arc3.langage import Programme
    import numpy as np
    s=source();c,d=proposer(s);_,(pc,sc)=c.rejouer()
    p=next(o for o in sc.sprites if 'piece' in o.get('tags',[]));p['pixels'][0,:]=14
    for q in sc.sprites:
        if 'bloqueur' in q.get('tags',[]):q['pixels']=np.full_like(q['pixels'],-1)
    Programme({'mode':'lois','etat':{},'regles':[c.programme['regles'][-1]]}).step(sc,('OBSERVE',))
    assert (p['pixels'][0,:]==14).all()

def test_ecart_hors_face_refuse():
    s=source();s.grilles[-1][10][10]=0
    assert proposer(s)[0] is None
