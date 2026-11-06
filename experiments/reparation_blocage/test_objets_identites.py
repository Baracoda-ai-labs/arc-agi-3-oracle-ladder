"""Identités sans cible : exemples fabriqués et préfixe causal indépendant du suffixe."""
import json
from pathlib import Path
import numpy as np
import pytest
from objets_identites import suivre_motif
from objets_variables import ObjetsVariables
from chrysalide.arc3.masque import Masque


def image(points, taille=2):
    g = np.zeros((64, 64), dtype=np.int16)
    for x,y in points:
        g[y:y+taille,x:x+taille] = 7
    return g


@pytest.mark.parametrize('n',[2,3,5])
def test_cardinalite_variable_identites_sans_but(n):
    points = [(4+10*i,20) for i in range(n)]
    gs = [image([(x+dx,y+dy) for x,y in points]) for dx,dy in [(0,0),(1,0),(1,1),(0,1),(0,0)]]
    with pytest.raises(ValueError,match='Aucun objet mobile'):
        ObjetsVariables(gs,[4,2,3,1])
    v = ObjetsVariables(gs,[4,2,3,1],identites_temporelles=True)
    assert len(v.mobiles)==n
    assert v.buts==[]  # Perception autorisée sans cible ; aucune victoire inventée.
    assert v.positions_observees(gs[0])==points
    assert v.positions_observees(gs[2])==[(x+1,y+1) for x,y in points]
    with pytest.raises(ValueError,match='unique'):
        v.scene(image([(x+2,y+2) for x,y in points]))  # Nouvelle observation encore non appariée.


def test_ambiguite_egale_reste_inconnue():
    gs=[image([(10,12),(14,12)]),image([(12,10),(12,14)])]
    with pytest.raises(ValueError,match='ambigu'):
        suivre_motif(gs,np.full((2,2),7),2)


def test_occlusion_reste_inconnue():
    gs=[image([(10,12),(20,12)]),image([(10,12)])]
    with pytest.raises(ValueError,match='occultation'):
        suivre_motif(gs,np.full((2,2),7),2)


def test_masque_court_ne_cache_pas_mobile_qui_revient():
    m=Masque(court=True)
    gs=[image([(10+x,12)],taille=2) for x in [0,1,2,1,0]]
    for a,b in zip(gs,gs[1:]):m.observer(a.tolist(),b.tolist())
    assert not m.cellules()


def test_masque_court_etend_compteur_monotone_seulement():
    gs=[]
    for t in range(5):
        g=image([(10+(t%2),12)],taille=2)
        g[63,:4*t]=3
        gs.append(g)
    m=Masque(court=True)
    for a,b in zip(gs,gs[1:]):m.observer(a.tolist(),b.tolist())
    assert m.cellules()==frozenset((63,x) for x in range(64))


def test_prefixe_m0r0_causal_et_transition_tenue_a_part():
    r=Path(__file__).parent/'runs/multijeux_nuit_integre1/m0r0/N1/partie'
    if not r.with_suffix('.npz').exists():pytest.skip('Archive locale absente')
    z=np.load(r.with_suffix('.npz'));j=json.loads(r.with_suffix('.json').read_text())
    gs=list(z['images'][:9]);actions=j['actions'][:8]
    v=ObjetsVariables(gs,actions,identites_temporelles=True,masque_court=True)
    assert len(v.mobiles)==2 and not v.buts
    # La transition12 n'est jamais transmise au constructeur : contrôle de mouvement,
    # sans se servir de sa réussite/son issue pour induire une règle ou un but.
    from objets_identites import occurrences
    avant,apres=z['images'][11:13]
    direction=j['actions'][11]
    positions=occurrences(avant,v.mobiles[0])
    assert len(positions)==len(v.mobiles)
    predictions=sorted((x+v.mouvements[i][direction][0],y+v.mouvements[i][direction][1]) for i,(x,y) in enumerate(positions))
    assert predictions==occurrences(apres,v.mobiles[0])
    assert v.buts==[]
