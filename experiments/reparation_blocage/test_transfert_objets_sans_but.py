import copy,json
from pathlib import Path
import cloudpickle,numpy as np
from transfert_objets_sans_but import reaffecter
from chaine_agent_integree import canon

R=Path(__file__).parent

def donnees():
    c=cloudpickle.loads((R/'runs/ar25_contexte_alternatif_archive22/candidat.pkl').read_bytes())
    z=np.load(R/'runs/transfert_modele_commun_ar25_1/N2/partie.npz')
    return c,z


def test_bord_et_autres_positions_observees_sans_reapprentissage():
    source,z=donnees();p=copy.deepcopy(source.programme);m=copy.deepcopy(source.perception.mouvements)
    initiales=copy.deepcopy(source.perception.initiales)
    for k in [0,6]:
        c,d=reaffecter(source,z['images'][k])
        assert d['admis'] and not d['but_ajoute'] and d['mouvements_reappris']==0
        assert any(y==0 for x,y in c.perception.initiales)
        assert c.perception.initiales!=initiales
        assert c.programme==p and c.perception.mouvements==m and not c.perception.buts
        _,(pc,sc)=c.rejouer();pc.step(sc,canon(2))
        assert np.array_equal(c.perception.rendu(sc),c.perception.vue(z['images'][k+1]))
    assert source.programme==p and source.perception.initiales==initiales


def test_ambiguite_et_regle_modifiee_refusees():
    source,z=donnees();im=z['images'][0].copy();motif=source.perception.mobiles[0]
    h,w=motif.shape;bloc=im[:h,42:42+w];bloc[motif>=0]=motif[motif>=0]
    assert reaffecter(source,im)[0] is None
    source.programme=copy.deepcopy(source.programme);source.programme['regles'][0]['phase']=7
    assert reaffecter(source,z['images'][0])[0] is None


def test_pixel_non_explique_et_contexte_incompatible_refuses():
    source,z=donnees();im=z['images'][0].copy();im[10,10]=2
    assert reaffecter(source,im)[0] is None
    assert reaffecter(source,z['images'][3])[0] is None
