from pathlib import Path
import numpy as np
import pytest
from perception_silhouette_atlas import SilhouetteAtlas,atlas
from chrysalide.arc3.langage import Programme
from session_chaine_generique import nouvel_agent
from classification_prefixe import classifier
ROOT=Path(__file__).parent
TRACE=ROOT/'runs/couverture_20_n1_isolee_26-10_1/resultats/graine_0/bp35/session/N1/partie.npz'

def test_prefixe_seul_route_admission_et_suffixe_sans_reinduction():
    with np.load(TRACE) as z:
        gs=list(z['images'][:5]);films=[z[f'film_{k}'] for k in range(1,5)]
    desc=classifier(gs[:3],[3,4],films[:2])
    assert 'silhouette_atlas_navigation' in desc['capacites_a_essayer']
    assert desc['atlas_silhouette'][0]['miroir_horizontal']
    a=nouvel_agent(gs[:3],[3,4],films[:2],['continue']*2)
    a.reconstruire()
    assert any(e.get('nom')=='silhouette_atlas' and e['type']=='admission' for e in a.journal)
    v=SilhouetteAtlas(gs[:3],[3,4]);p=Programme(v.programme());sc=v.scene(gs[0])
    assert np.array_equal(v.rendu(sc),v.vue(gs[0]))
    from jauges_observees import jauges_validees
    admises,rapports=jauges_validees(gs[:3],[3,4])
    assert not admises
    regions_candidates={tuple(p) for r in rapports for p in r['region']}
    erreurs=[]
    for act,g in zip([3,4,3,4],gs[1:]):
        p.step(sc,('LEFT' if act==3 else 'RIGHT',));diff=v.rendu(sc)!=g
        # Le HUD n'est PAS masqué avant la preuve minimale de jauge.
        erreurs.append(np.argwhere(diff).tolist())
        assert len(erreurs[-1])<=4
        assert set(map(tuple,erreurs[-1])) <= regions_candidates
    assert 'silhouette_atlas' not in a.chaines  # rendu total incomplet : refus conservé
    assert v.contradictions_statiques

def test_ambiguite_deux_silhouettes_refusee():
    with np.load(TRACE) as z:gs=list(z['images'][:3])
    v=SilhouetteAtlas(gs,[3,4]);g=gs[0].copy();m=v.empreintes[0];g[10:10+m.shape[0],10:10+m.shape[1]]=np.where(m>=0,m,g[10:10+m.shape[0],10:10+m.shape[1]])
    with pytest.raises(ValueError):v.scene(g)

def test_orientation_identique_conservee():
    with np.load(TRACE) as z:g=z['images'][0]
    gs=[g,np.roll(g,-6,axis=1),np.roll(g,-12,axis=1)]
    _,_,_,preuves=atlas(gs,[3,3])
    assert all(p['orientation_identique'] and not p['miroir_horizontal'] for p in preuves)
