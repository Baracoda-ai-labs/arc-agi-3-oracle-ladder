import json
from pathlib import Path
import numpy as np
import pytest
from atlas_motifs_partiel import AtlasMotifsPartiel


def donnees():
    p=Path(__file__).parent/'runs/transfert_commun_cd82_1/reel/N1/partie'
    z=np.load(p.with_suffix('.npz'));a=json.loads(p.with_suffix('.json').read_text())['actions']
    return z,a


def evaluer(transform=lambda x:x):
    z,a=donnees()
    def propre(im):
        g=im.copy();g[-1]=int(np.bincount(g.ravel()).argmax());return transform(g)
    gs=[propre(g) for g in z['images']];fs=[[propre(g) for g in z[f'film_{i+1}']] for i in range(len(a))]
    m=AtlasMotifsPartiel(gs[:5],a[:4],fs[:4]);out=[]
    tables=dict(m.tables)
    for i in range(4,len(a)):
        m.predire(a[i]);r=m.observer(a[i],gs[i+1],fs[i]);out.extend((i+1,x['verdict']) for x in r)
    assert dict(m.tables)==tables  # aucun apprentissage du suffixe
    return out


def test_suffixe_connu_seulement():
    assert evaluer()==[(7,'compatible')]*2+[(8,'compatible')]*2


def test_palette_bijective():
    assert evaluer(lambda g:15-g)==evaluer()


def test_translation_image_sans_coupure():
    assert evaluer(lambda g:np.roll(g,(1,1),(0,1)))==evaluer()


def test_refus_absence_prediction_et_masque_non_prouve():
    z,a=donnees()
    with pytest.raises(ValueError):AtlasMotifsPartiel(z['images'][:5],a[:4],[z[f'film_{i}'] for i in range(1,5)],[(63,0)])
    m=AtlasMotifsPartiel(z['images'][:5],a[:4],[z[f'film_{i}'] for i in range(1,5)])
    with pytest.raises(ValueError):m.observer(a[4],z['images'][5],z['film_5'])
