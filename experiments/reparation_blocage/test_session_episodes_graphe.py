from types import SimpleNamespace
import numpy as np
import pytest
import session_chaine_generique as session


def test_episodes_separes_copies_sans_fusion_et_ancien_snapshot():
    g=np.zeros((4,4),dtype=int)
    ancien=SimpleNamespace(images=[g,g.copy()],actions=[['clic',1,2]],issues=['defaite'])
    un=session.observations_tentatives(ancien)
    assert len(un)==1 and un[0]['actions']==[['clic',1,2]]
    suivant=SimpleNamespace(images=[g.copy(),g.copy()],actions=[2],issues=['defaite'],observations_episodes=un)
    deux=session.observations_tentatives(suivant)
    ancien.images[0][0,0]=8;ancien.actions[0][1]=3
    un[0]['grilles'][0][1,1]=7;suivant.images[0][2,2]=9
    assert deux[0]['actions']==[['clic',1,2]]
    assert np.count_nonzero(deux[0]['grilles'][0])==0
    assert np.count_nonzero(deux[1]['grilles'][0])==0
    assert [e['actions'] for e in deux]==[[['clic',1,2]],[2]]
    assert all(len(e['grilles'])==len(e['actions'])+1 for e in deux)


def test_reset_et_episode_desaligne_refuses():
    a=SimpleNamespace(images=[[],[]],actions=[0],issues=['continue'])
    with pytest.raises(ValueError,match='RESET'):session.observations_tentatives(a)
    a.actions=[]
    with pytest.raises(ValueError,match='aligne'):session.observations_tentatives(a)


def test_retenter_transmet_observations_et_preserve_risque_terminal(tmp_path,monkeypatch):
    from test_retry_episodes import test_retry_deux_episodes_compte_reset_sans_transition_fictive
    original=session.nouvel_agent;nouveaux=[]
    def capturer(*args,**kw):
        a=original(*args,**kw);nouveaux.append(a);return a
    monkeypatch.setattr(session,'nouvel_agent',capturer)
    test_retry_deux_episodes_compte_reset_sans_transition_fictive(
        tmp_path,monkeypatch,'{"op":"retry"}\n{"op":"advance","coups":1}\n')
    nouveau=nouveaux[-1]
    assert nouveau.actions==[2] and nouveau.issues==['victoire']
    assert len(nouveau.observations_episodes)==1
    episode=nouveau.observations_episodes[0]
    assert episode['actions']==[1] and episode['issues']==['defaite']
    assert len(episode['grilles'])==2
    assert nouveau.memoire_episodes[0]['statut']=='risque_provisoire'
    nouveau.images[0][0,0]=9
    assert episode['grilles'][0][0,0]==0
