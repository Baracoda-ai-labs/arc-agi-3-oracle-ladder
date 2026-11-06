from types import SimpleNamespace
import numpy as np
from chrysalide.arc3.logique.theorie import Theorie,VOISINS8
from chrysalide.arc3.logique.distance_bascule import pour_theorie


def exemple():
    f=frozenset((x,y) for x in range(3) for y in range(3))
    point=frozenset({(0,0)})
    monde=[(12,point,5,5)]
    monde += [(2 if (dx,dy)==(1,1) else 0,point,5+dx,5+dy) for dx,dy in VOISINS8]
    monde += [(9,f,4+4*dx,4+4*dy) for dx,dy in VOISINS8]
    th=Theorie(bascule={9:8,8:12,12:9},motif=frozenset({(0,0)}),formes_bascule=frozenset({f}),but=('motif_rel',0,2))
    sprites=[]
    for c,forme,x,y in monde:
        p=np.full((max(y for _,y in forme)+1,max(x for x,_ in forme)+1),-1)
        for dx,dy in forme:p[dy,dx]=c
        sprites.append(dict(x=x,y=y,pixels=p,visible=True))
    return th,tuple(monde),SimpleNamespace(sprites=sprites)


def test_distance_compte_transitions_pas_seulement_erreurs():
    th,monde,scene=exemple();score=pour_theorie(th,monde)
    assert score(scene,{})==14
    tuile=next(s for s in scene.sprites if s['x']==0 and s['y']==0)
    tuile['pixels'][:]=8
    assert score(scene,{})==13
    tuile['pixels'][:]=12
    assert score(scene,{})==12
    assert th.bascule=={9:8,8:12,12:9}


def test_pas_de_score_pour_clics_couples_ou_mouvement():
    th,monde,_=exemple();th.motif=frozenset({(0,0),(4,0)})
    assert pour_theorie(th,monde) is None
    th.motif=frozenset({(0,0)});th.moves={(9,1):(0,-1)}
    assert pour_theorie(th,monde) is None


def test_but_inaccessible_pas_de_distance_inventee():
    th,monde,_=exemple();th.bascule={9:8,8:9}
    assert pour_theorie(th,monde) is None
