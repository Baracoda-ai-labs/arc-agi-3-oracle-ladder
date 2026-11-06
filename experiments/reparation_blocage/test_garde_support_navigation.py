import json
from pathlib import Path
import numpy as np
from objets_variables import ObjetsVariables
from garde_support_navigation import apprendre,proposer


def donnees(n=46):
 p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_trace46/partie'
 actions=json.loads(p.with_suffix('.json').read_text())['actions'][:n]
 with np.load(p.with_suffix('.npz')) as z:im=list(z['images'][:n+1].copy())
 motif=ObjetsVariables(im[20:36],actions[20:35]).mobiles[0]
 return im,actions,motif


def test_gardes_apprises_sans41_predisent_blocage41():
 im,a,m=donnees(40);g,_,_=apprendre(im,a,m)
 assert len(g)==6
 assert all(int(im[-1][56+r['offset'][1],36+r['offset'][0]]) in r['bloques_observes'] for r in g)


def test_route_nouvelle_depuis46_reutilise_retour_observe():
 im,a,m=donnees();d=proposer(im,a,m,[1,2,3,4,6,7])
 assert d['actions']==[1]
 assert d['route_acces_hypothetique']==[1,1,4,4,4,4]
 assert d['cible_nouveaute']==[36,32]
 assert not d['contrat_prediction_partielle']['but_certifie']
 assert proposer(im,a,m,[6,7]) is None


def test_invariance_couleur_sans_regle_de_couleur_imposee():
 im,a,m=donnees();p=np.arange(16)[::-1]
 mm=m.copy();mm[m>=0]=p[m[m>=0]]
 assert proposer([p[x] for x in im],a,mm,[1,2,3,4])['route_acces_hypothetique']==proposer(im,a,m,[1,2,3,4])['route_acces_hypothetique']
