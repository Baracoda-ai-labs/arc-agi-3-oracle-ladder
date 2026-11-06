from pathlib import Path
import copy, cloudpickle
from chaine_coherente import Chaine
from revision_sol_revele import proposer
BASE=Path(__file__).parent/'runs'

def source():
    return cloudpickle.loads((BASE/'ka59_n3_sol46_auto1/source46_refute.pkl').read_bytes())

def test_sol_seul_et_but_conserve():
    s=source();p=copy.deepcopy(s.programme);c,d=proposer(s)
    assert c and d['pixels_reveles']==45
    assert d['controle']['transitions']==46 and d['controle']['compilation_fidele']
    assert c.programme==p==s.programme
    assert c.preuve_but_elargi==s.preuve_but_elargi and c.but_hypothese_non_confirmee

def test_ecart_hors_support_refuse():
    s=source();s.grilles[-1][10][10]=7
    assert proposer(s)[1]['refus']=='ecart_hors_support_libere'

def test_sol_non_libre_refuse():
    s=source();s.grilles[-1][20][53]=7
    assert proposer(s)[1]['refus']=='sol_non_etabli'
