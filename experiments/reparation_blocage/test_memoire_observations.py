import numpy as np
import pytest
from types import SimpleNamespace
from session_chaine_generique import observations_tentatives
from memoire_observations import episode_observe


def test_films_intermediaires_conserves_et_empreinte_sensible():
    g=np.zeros((4,4),dtype=int);f=np.array([g,g.copy()]);f[0,1,1]=3
    a=SimpleNamespace(images=[g,g],actions=[2],issues=['continue'],films=[f])
    ep=observations_tentatives(a)[0]
    idem=episode_observe([g.tolist(),g.tolist()],[2],['continue'],[f.tolist()])
    assert ep['provenance']==idem['provenance']
    f[0,1,1]=4
    assert ep['films'][0][0,1,1]==3
    assert observations_tentatives(a)[0]['provenance']!=ep['provenance']


def test_films_manquants_explicitement_et_mauvais_alignement_refuse():
    ep=episode_observe([[],[]],[1],['continue'])
    assert ep['films'] is None and not ep['provenance']['films_disponibles']
    with pytest.raises(ValueError,match='Films'):episode_observe([[],[]],[1],['continue'],[])
    with pytest.raises(ValueError,match='RESET'):episode_observe([[],[]],[np.int64(0)],['continue'])


def test_import_dedoublonne_verifie_et_ne_modifie_pas_agent_courant():
    from memoire_observations import ajouter_episode
    a=SimpleNamespace(images=['etat courant'],actions=[],chaines={'modele':'conserve'})
    ep=episode_observe([[],[]],[1],['continue'])
    assert ajouter_episode(a,ep) and not ajouter_episode(a,ep)
    ep['actions'][0]=2
    with pytest.raises(ValueError,match='Empreinte'):ajouter_episode(a,ep)
    assert a.observations_episodes[0]['actions']==[1]
    assert a.images==['etat courant'] and a.chaines=={'modele':'conserve'}


def test_import_archive_films_et_frontiere(tmp_path):
    import hashlib,json
    from memoire_observations import lire_archive
    p=tmp_path/'trace';g=np.zeros((3,4,4),dtype=int)
    np.savez(p.with_suffix('.npz'),images=g,film_1=g[:1],film_2=g[1:])
    rows=[{'action':1,'state':'NOT_FINISHED','levels_completed':0},
          {'action':2,'state':'NOT_FINISHED','levels_completed':1}]
    def ecrire():
        p.with_suffix('.json').write_text(json.dumps({'rows':rows}))
        return {s:hashlib.sha256(p.with_suffix(s).read_bytes()).hexdigest() for s in ('.npz','.json')}
    h=ecrire();ep=lire_archive(p,h,0)
    assert ep['issues']==['continue','niveau'] and len(ep['films'])==2
    rows[0]['levels_completed']=1
    h2=ecrire()
    with pytest.raises(ValueError,match='Empreinte'):lire_archive(p,h,0)
    with pytest.raises(ValueError,match='frontiere'):lire_archive(p,h2,0)
