import numpy as np
from test_composition_depuis_observations import donnees
from revision_calques_contextes import proposer_avec_revision


def test_reutilisation_calques42_et_suffixe43_52_integral():
    a,p,alt=donnees()
    cs,d=proposer_avec_revision(p,alt,a.images,a.actions,a.issues,a.films)
    assert cs,d
    assert d['contre_exemple']==42 and d['suffixe_tenu_a_part']==[43,52]
    assert d['rejeu_integral'] and not d['programme_dynamique_modifie']
    assert len(cs)==2
    for c in cs:
        check,state=c.rejouer()
        assert state is not None and check['transitions']==52 and check['compilation_fidele']
        assert np.array_equal(c.perception.rendu(state[1]),c.perception.vue(a.images[52]))
    assert {len(c.perception.points) for c in cs}=={2,8}


def test_pixel_hors_cible_pas_absorbe():
    a,p,alt=donnees();images=[g.copy() for g in a.images];images[42][10,10]=2
    cs,d=proposer_avec_revision(p,alt,images,a.actions,a.issues,a.films)
    assert not cs
