import numpy as np
from compteurs_regions_observees import apprendre,prevoir

def test_cycle_exige_saturation_filmee_et_ne_couvre_pas_commande_inconnue():
    def g(n):return np.array([[7]*n+[9]*(3-n)])
    images=[g(1),g(2),g(0),g(1)]
    films=[[g(2)],[g(3),g(0)],[g(1)]]
    h=apprendre(images,films,[1,2,1],[[0,0],[0,1],[0,2]],[7,9])
    assert len(h)==1 and h[0]['periode_candidate']==3 and h[0]['provisoire']
    assert prevoir(h,1)[0]['compte']==2 and prevoir(h,4) is None
    assert apprendre(images,[[g(2)],[g(0)],[g(1)]],[1,2,1],[[0,0],[0,1],[0,2]],[7,9])==[]
