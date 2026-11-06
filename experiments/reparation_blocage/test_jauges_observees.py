"""Rejeu sans SDK ; les barres sont des hypothèses reconnues, pas une bordure imposée."""
import json
from pathlib import Path
import numpy as np
import pytest
from jauges_observees import jauges_validees, lecteur
from objets_variables import ObjetsVariables
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import NOMS


def test_barre_validee_et_scene_preservee():
    gs=[]
    for t in range(9):
        g=np.ones((64,64),dtype=np.int16)
        g[63,:64-t//2]=5
        g[15:17,10+t%2:12+t%2]=7
        g[30:35,40:45]=9
        gs.append(g)
    cells, rapports=jauges_validees(gs,[4,3]*4)
    assert cells==frozenset((63,x) for x in range(64))
    assert not any((y,x) in cells for y,x in np.argwhere(np.isin(gs[0],[7,9])))
    assert any(r['admis'] for r in rapports)


def test_decor_immobile_et_mobile_de_bord_non_masques():
    gs=[]
    for t in range(9):
        g=np.ones((64,64),dtype=np.int16)
        g[0,:]=5  # Décor statique : aucune dynamique de compteur démontrée.
        g[63,10+t%2:12+t%2]=7
        gs.append(g)
    assert not jauges_validees(gs,[4,3]*4)[0]


def test_recharge_reste_hypothese_non_admise():
    gs=[]
    for k in [0,1,2,3,0,1,2,3,0]:
        g=np.ones((64,64),dtype=np.int16);g[63,:64-k]=5;gs.append(g)
    assert not jauges_validees(gs,[4,3]*4)[0]


def test_prefixe_m0r0_admis_sans_but_et_suffixe_separe():
    p=Path(__file__).parent/'runs/multijeux_nuit_integre1/m0r0/N1/partie'
    if not p.with_suffix('.npz').exists():pytest.skip('Archive locale absente')
    z=np.load(p.with_suffix('.npz'));j=json.loads(p.with_suffix('.json').read_text())
    gs=list(z['images'][:9]);actions=j['actions'][:8]
    v=ObjetsVariables(gs,actions,identites_temporelles=True,jauge_validee=True)
    assert len(v.mobiles)==2 and v.buts==[]
    for image in gs:
        assert np.array_equal(v.vue(image)[1:63],image[1:63])
    c=Chaine(v,v.programme(),[g.tolist() for g in gs],
             [{'actions':[{'action':NOMS[a]}]} for a in actions],[(NOMS[a],) for a in actions])
    check,state=c.rejouer()
    assert state is not None and check['rejeu'] and check['compilation_fidele']
    frozen_hud=v.hud
    for rev in [False,True]:
        ims=[g[::-1].copy() if rev else g for g in z['images']]
        e=lecteur()(ims[0])
        for k in range(8):e.update(j['actions'][k],ims[k],ims[k+1])
        for k in range(8,32):
            e.update(j['actions'][k],ims[k],ims[k+1])
            assert e.rows[-1]['prediction_contains_observation']
        assert e.valid
    assert v.hud==frozen_hud and v.buts==[]  # Suffixe jamais réinjecté dans l'induction.
