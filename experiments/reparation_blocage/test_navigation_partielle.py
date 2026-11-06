import json
from pathlib import Path
import numpy as np
import pytest
from navigation_partielle import NavigationPartielle


def archive(n=2):
    p=Path(__file__).parent/'runs/bp35_navigation_visible_reprise1/N1/partie'
    z=np.load(p.with_suffix('.npz'));j=json.loads(p.with_suffix('.json').read_text())
    a=j['actions'];m=NavigationPartielle(z['images'][:n+1],a[:n],[z[f'film_{i+1}'] for i in range(n)],['continue']*n)
    return m,z,a,n


def test_prediction_prospective_limitee_et_compteur():
    m,z,a,n=archive();p=m.predire(a[n],[3,4,6])
    assert p['issue']=='inconnue' and 'pixels_complets' in p['inconnus'] and 'image' not in p
    r=m.observer(a[n],z['images'][n+1],z[f'film_{n+1}'],'continue')
    assert r['statut_partiel']=='compatible_sur_champs_observes'
    assert r['coups_deja_joues']==n+1 and not r['issue_couverte']


def test_divergence_elimine_seulement_hypotheses_refutees():
    m,z,a,n=archive(3);old=set(m.h.actives());m.predire(a[n],[3,4,6])
    r=m.observer(a[n],z['images'][n+1],z[f'film_{n+1}'],'continue')
    bad={x['hypothese'] for x in r['comparaisons'] if not x['conforme']}
    assert bad and set(m.h.actives())==old-bad


def test_terminal_ne_refute_pas_gravite():
    m,z,a,n=archive();old=m.h.actives();m.predire(a[n],[3,4,6])
    r=m.observer(a[n],z['images'][n+1],z[f'film_{n+1}'],'defaite')
    assert m.h.actives()==old and r['plan_invalide'] and r['statut_partiel']=='issue_non_modelisee'


def test_image_ininterpretable_n_est_pas_refutation():
    m,z,a,n=archive();old=m.h.actives();m.predire(a[n],[3,4,6])
    r=m.observer(a[n],np.zeros_like(z['images'][n+1]),[],'continue')
    assert r['statut_partiel']=='observation_non_comparable' and m.h.actives()==old


def test_pas_observation_sans_prediction_et_prediction_figee():
    m,z,a,n=archive()
    with pytest.raises(ValueError):m.observer(a[n],z['images'][n+1],[],'continue')
    p=m.predire(a[n],[3,4,6]);p['actions'][0]=999
    with pytest.raises(ValueError):m.predire(a[n],[3,4,6])
    m.h.catalogue.clear()  # ne doit pas modifier le modèle prospectif déjà figé
    r=m.observer(a[n],z['images'][n+1],z[f'film_{n+1}'],'continue')
    assert r['actives']


def test_offre_et_catalogue_obligatoires():
    m,z,a,n=archive()
    for action,offre in [(4,[3]),(['autre',1,2],[6]),(['clic',64,2],[6]),(1,[1])]:
        with pytest.raises(ValueError): m.predire(action,offre)
    assert m.attente is None
    with pytest.raises(ValueError):
        NavigationPartielle(z['images'][:3],[1,4],[[],[]],['continue']*2)


def test_exception_apres_revocation_est_transactionnelle(monkeypatch):
    from hypotheses_navigation import HypothesesNavigation
    m,z,a,n=archive();old=m.h.actives();m.predire(a[n],[3,4,6])
    def observer(self,*args):
        self.atms.interdire([self.actives()[0]])
        raise ValueError('Erreur apres revocation partielle')
    monkeypatch.setattr(HypothesesNavigation,'observer',observer)
    r=m.observer(a[n],z['images'][n+1],[],'continue')
    assert m.h.actives()==old and r['actives']==old
    assert r['statut_partiel']=='observation_non_comparable'


def test_decider_refuse_proposeur_hors_offre(monkeypatch):
    m,z,a,n=archive()
    monkeypatch.setattr(m.h,'proposer',lambda *args:{'action':4,'raison':'test'})
    with pytest.raises(ValueError): m.decider([3])
    assert m.attente is None
