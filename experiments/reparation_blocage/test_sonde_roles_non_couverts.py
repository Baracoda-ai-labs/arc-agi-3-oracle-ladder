import copy
from pathlib import Path
import cloudpickle
import numpy as np
from sonde_roles_non_couverts import proposer


def archive():
    import tarfile
    with tarfile.open(Path(__file__).parent/'archives/ka59_n3_but_reouvert16.tar.gz') as t:
        return cloudpickle.loads(t.extractfile('runs/ka59_n3_but_reouvert8_1/agent.pkl').read())


def test_sonde_reelle_cible_forme_ignoree_sans_modifier_modele():
    a=archive(); c=next(iter(a.chaines.values())); avant=copy.deepcopy(c.programme)
    e,d=proposer(c,a.images,a.actions,[1,2,3,4,6])
    assert e and e['actions'][0][0]=='clic' and d['candidats_non_repetes']>0
    assert c.programme==avant and c.plan is None
    assert np.array_equal(e['predictions'][0][0]['image'],c.perception.vue(a.images[-1]))
    assert not d['modele_alternatif_admis']


def test_episode_deja_observe_elimine_la_meme_question():
    a=archive();c=next(iter(a.chaines.values()))
    e,_=proposer(c,a.images,a.actions,[1,2,3,4,6])
    ep={'grilles':[a.images[-1],a.images[-1]],'actions':e['actions']}
    autre,_=proposer(c,a.images,a.actions,[1,2,3,4,6],[ep])
    assert autre is None or autre['actions']!=e['actions']
    assert proposer(c,a.images,a.actions,[1,2,3,4])[0] is None


def test_decider_raccorde_prediction_avant_experience():
    from pathlib import Path
    from avancer_agent_relais import charger_agent
    a=archive()
    assert len(a.actions)==16
    d=a.decider([1,2,3,4,6],secondes=5)
    assert d['statut']=='experience_role_non_couvert'
    assert d['modeles']==list(a.chaines)
    assert a.attente is d and all(c.plan for c in a.chaines.values())
    assert len(a.actions)==16
