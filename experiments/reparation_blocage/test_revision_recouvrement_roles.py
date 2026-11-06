from pathlib import Path
import copy,cloudpickle
from revision_recouvrement_roles import proposer
P=Path(__file__).parent/'runs/ka59_n4_recouvrement34_auto1/source34_refute.pkl'

def test_recouvrement_sol_et_source():
 s=cloudpickle.loads(P.read_bytes());p=copy.deepcopy(s.programme);sig=s.perception.signature_observation();c,d=proposer(s)
 assert c and d['controle']['transitions']==34 and d['sources'][0]['transitions']==62
 assert d['sol']['pixels_reveles']==45 and d['sol']['controle']['compilation_fidele']
 assert c.programme==p==s.programme and c.preuve_but_elargi==s.preuve_but_elargi
 assert c.preuve_transfert_roles==s.preuve_transfert_roles
 assert c.perception.signature_observation()!=sig and s.perception.signature_observation()==sig

def test_erreur_sans_support_refusee():
 s=cloudpickle.loads(P.read_bytes());s.grilles[-1][10][10]=7
 assert proposer(s)[0] is None

def test_pas_de_cible_ne_pose_pas_calque():
 s=cloudpickle.loads(P.read_bytes());s.perception.cibles=[]
 assert proposer(s)[0] is None
