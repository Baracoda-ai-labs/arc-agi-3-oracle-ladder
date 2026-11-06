from pathlib import Path
import numpy as np
from referentiel_visible import estimer
from avancer_agent_relais import charger_agent
from relation_clic_observee import actualiser

def test_deux_axes_sur_recouvrement_sans_bouclage_pixels():
    a=np.repeat(np.random.default_rng(72).integers(0,5,size=(64,1)),64,axis=1)
    a[:,[5,17,28,49]]=[6,7,8,9];b=np.zeros_like(a)
    b[:34,15:]=a[30:,:49]
    r=estimer(a,b,{11,12,14})
    assert r['translation']==[15,-30] and r['erreur']==0
    assert not r['camera_certifiee']

def test_film_archive52_rouvre_relation_locale_sans_certifier_victoire():
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_relation51/agent.pkl')
    m=actualiser(a)
    assert not m['refutee']
    assert m['reouverture_champ_commun']['referentiel']['translation']==[15,-30]
    assert a.diagnostics_champ_commun[-1]['attendu_local']==[[39,18]]
    assert not m['population_totale_verifiee'] and not m['but_certifie']


def test_texture_sans_ancre_alignable_abstient_plutot_que_certifier():
    a=np.random.default_rng(72).integers(0,10,size=(64,64));b=np.zeros_like(a);b[:34,15:]=a[30:,:49]
    assert not estimer(a,b,{11,12,14})['retenu']
