from pathlib import Path
import cloudpickle,copy
from revision_faces_contact import proposer

P=Path(__file__).parent/'runs/ka59_n3_roles_buts45_auto1/source45_avant_revision.pkl'

def test_face_entiere_noire_avec_coin_deja_correct():
    s=cloudpickle.loads(P.read_bytes());old=copy.deepcopy(s.programme)
    c,d=proposer(s)
    assert c and d['orientation']==[0,3] and d['pixels_observes']==3
    assert d['controle']['transitions']==45 and d['controle']['compilation_fidele']
    assert c.programme['regles'][:-1]==old['regles']
    assert c.but_inconnu and c.preuve_classe_glissable==s.preuve_classe_glissable
    assert c.preuve_revision_but==s.preuve_revision_but and s.programme==old

def test_face_non_uniforme_refusee_meme_si_erreurs_locales():
    s=cloudpickle.loads(P.read_bytes());s.grilles[-1][22][51]=7
    assert proposer(s)[0] is None
