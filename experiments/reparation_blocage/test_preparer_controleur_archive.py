import json
from types import SimpleNamespace
import numpy as np
import pytest
import preparer_controleur_archive as p
from avancer_agent_relais import charger_agent


def archive(tmp_path):
    source=tmp_path/'source';(source/'N1').mkdir(parents=True)
    (source/'etat.json').write_text(json.dumps({'niveau':1,'tentative':1,'jeu':'faux','coups_reels':2,'graine_exploration':7}))
    (source/'journal.json').write_text(json.dumps([{'type':'preuve','contenu':'conserver'}]))
    rows=[{'action':a,'state':'NOT_FINISHED','levels_completed':0} for a in (1,2)]
    (source/'N1/partie.json').write_text(json.dumps({'rows':rows}))
    images=np.arange(3*16).reshape(3,4,4)
    np.savez(source/'N1/partie.npz',images=images,film_1=images[1:2],film_2=images[2:3])
    return source


def test_preserve_observations_sans_sdk_et_signale_reconstruction(tmp_path,monkeypatch):
    source=archive(tmp_path)
    def creer(images,actions,films,issues,graine_exploration):
        return SimpleNamespace(images=images,actions=actions,films=films,issues=issues,
          graine_exploration=graine_exploration,commandes_connues=set(),attente=None)
    monkeypatch.setattr(p,'nouvel_agent',creer)
    rapport=p.preparer(source,tmp_path/'out')
    a=charger_agent(tmp_path/'out/agent.pkl')
    assert a.actions==[1,2] and a.commandes_connues=={1,2} and a.graine_exploration==7
    assert a.journal[0]['type']=='preuve' and len(a.films)==2
    assert rapport['initialisations_sdk']==rapport['reacces_effectue']==0
    assert not rapport['meme_instance'] and not rapport['sdk_rattache']
    assert rapport['pertes_ou_revalidation']


def test_refuse_episode_avec_reset_ou_compteur_desaligne(tmp_path):
    source=archive(tmp_path)
    path=source/'etat.json';d=json.loads(path.read_text());d['tentative']=2;path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='premier épisode'):p.preparer(source,tmp_path/'out')
    assert not (tmp_path/'out').exists()
