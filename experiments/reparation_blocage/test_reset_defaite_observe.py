"""Contrat RESET observé ; aucune création ni exécution de jeu."""
import json
import time
from types import SimpleNamespace
import numpy as np
import pytest
from boucle_objets_variables import LaboP1
import chrysalide.arc3.logique.jeux as jeux


def labo(tmp_path):
    l=object.__new__(LaboP1)
    l.env=object();l.finished=True;l.won=False;l.partie_gagnee=False
    l.image=np.zeros((64,64),dtype=int);l.images=[l.image.copy()];l.films={};l.rows=[]
    l.start=time.monotonic();l.completed_baseline=1;l.resets=0;l.defaites=1
    l.output=tmp_path/'partie';l.game='faux';l.level=2;l.injected=False
    l.actions_disponibles=[1]
    return l


@pytest.mark.parametrize('state,completed,finished,won',[
    ('NOT_FINISHED',1,False,False),('GAME_OVER',1,True,False),('WIN',2,True,True)])
def test_reset_archive_film_offre_et_issue_reelle(tmp_path,monkeypatch,state,completed,finished,won):
    l=labo(tmp_path);env=l.env;calls=[]
    frames=np.array([np.ones((64,64),dtype=int),np.full((64,64),2,dtype=int)])
    def jouer(e,a):
        calls.append((e,a))
        return SimpleNamespace(frame=frames,available_actions=[4,6],levels_completed=completed,state=state)
    monkeypatch.setattr(jeux,'jouer_action',jouer)
    l.reset_apres_defaite()
    assert calls==[(env,0)] and l.resets==1 and len(l.rows)==1
    assert l.actions_disponibles==[4,6] and l.finished==finished and l.won==won
    assert l.defaites==(2 if state=='GAME_OVER' else 1)
    assert l.rows[0]['state']==state and l.rows[0]['action']==0
    with np.load(l.output.with_suffix('.npz')) as z:
        assert np.array_equal(z['film_1'],frames)
    assert json.loads(l.output.with_suffix('.json').read_text())['rows'][0]['levels_completed']==completed


@pytest.mark.parametrize('finished,won,partie',[(False,False,False),(True,True,False),(True,True,True)])
def test_reset_refuse_sans_defaite_avant_sdk(tmp_path,monkeypatch,finished,won,partie):
    l=labo(tmp_path);l.finished=finished;l.won=won;l.partie_gagnee=partie
    def interdit(*args):raise AssertionError('SDK interdit')
    monkeypatch.setattr(jeux,'jouer_action',interdit)
    with pytest.raises(ValueError,match='défaite observée'):l.reset_apres_defaite()
    assert not l.rows and l.resets==0
