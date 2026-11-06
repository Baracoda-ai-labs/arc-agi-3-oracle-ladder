import numpy as np
import pytest
from corpus_decouverte import exemple

def test_futur_separe_et_pas_de_fausse_bonne_action():
    images=np.array([[[0]],[[1]],[[2]]])
    films=[images[1:2],images[2:3]]
    d={'actions':[1],'predictions':[]}
    ident, entree, cible=exemple(images,films,[1,1],2,d,{'resultats':[]})
    changed=images.copy();changed[2]=9
    ident2, entree2, cible2=exemple(changed,[films[0],changed[2:3]],[1,1],2,d,{'resultats':[]})
    assert ident==ident2 and entree==entree2
    assert cible['film_resultat_sha256']!=cible2['film_resultat_sha256']
    assert not cible['imitation_action_autorisee']
    assert cible['action_optimale'] is None
    assert entree['actions_passees']==[1]

def test_rejette_mauvais_alignement():
    im=np.array([[[0]],[[1]]])
    with pytest.raises(ValueError,match='aligné'):
        exemple(im,[im[:1]],[1],1,{'actions':[1]}, {})
