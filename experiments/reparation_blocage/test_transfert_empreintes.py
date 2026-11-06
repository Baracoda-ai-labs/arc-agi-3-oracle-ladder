from pathlib import Path
import pickle
import numpy as np
import pytest
from apprendre_empreintes import apprendre
from loi_orientation import prefixe
from transfert_empreintes import lier,planifier
R=Path(__file__).parent

@pytest.fixture(scope='module')
def modele():
 base=R/'runs/transfert_commun_cd82_1/reel/N1/partie';_,_,ids,_,_,_=prefixe(base,[])
 return apprendre([base,R/'runs/session_perception_arc1/N1/partie'],ids,exporter=True)

def test_reaffectation_transfert_sans_modifier_regles(modele):
 im=np.load(R/'runs/session_perception_arc1/N2/partie.npz')['images'][0];before=pickle.dumps(modele)
 b=lier(modele,im);r,p=planifier(modele,b,[im],[])
 assert p and len(b['selectors'])>len(modele['selectors'])
 assert b['pistes']!=modele['pistes'] and r['modeles_visuels_candidats']==1
 assert r['regles_reapprises']==0 and before==pickle.dumps(modele)

def test_translation_reaffecte_positions(modele):
 im=np.load(R/'runs/session_perception_arc1/N2/partie.npz')['images'][0];b=lier(modele,im);c=lier(modele,np.roll(im,2,axis=1))
 assert c['box']==tuple(v+2 if i%2==0 else v for i,v in enumerate(b['box']))
 for color,(_,x,y) in b['selectors'].items():assert c['selectors'][color]==['clic',x+2,y]

def test_contour_absent_ne_reutilise_pas_ids(modele):
 with pytest.raises(ValueError):lier(modele,np.zeros((64,64),dtype=np.uint8))
