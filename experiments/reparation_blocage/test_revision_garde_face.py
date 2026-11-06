import copy,cloudpickle
from pathlib import Path
from revision_garde_face import proposer
P=Path(__file__).parent/'runs/ka59_n3_garde_face52_auto1/source52_refute.pkl'

def test_garde_minimale_et_prefixe_entier():
    s=cloudpickle.loads(P.read_bytes());p=copy.deepcopy(s.programme);c,d=proposer(s)
    assert c and d['controle']['transitions']==52 and d['controle']['compilation_fidele']
    assert s.programme==p and c.but_inconnu==s.but_inconnu
    changements=[(a,b) for a,b in zip(p['regles'],c.programme['regles']) if a!=b]
    assert changements and all(a['nom'].startswith('face_support_') for a,b in changements)
    assert any(a['nom']==d['regle'] for a,b in changements)
    assert c.preuve_classe_glissable==s.preuve_classe_glissable

def test_ancien_contre_exemple_ne_sefface_pas():
    s=cloudpickle.loads(P.read_bytes());s.grilles[40][10][10]=7
    assert proposer(s)[1]['refus']=='prefixe_deja_refute'

def test_ecart_hors_face_refuse():
    s=cloudpickle.loads(P.read_bytes());s.grilles[-1][10][10]=7
    assert proposer(s)[0] is None
