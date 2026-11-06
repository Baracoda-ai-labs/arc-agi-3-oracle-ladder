import copy
import cloudpickle as pickle
from test_revision_sans_effet import monde, etendre
from revision_sans_effet import proposer
from chaine_agent_integree import AgentIntegre


def preparer(monde):
    c,g,a=monde
    c,diag=proposer(etendre(c,g,a,11))
    assert diag['admis']
    agent=AgentIntegre(g[:12],a[:11],[[im.tolist()] for im in g[1:12]],['continue']*11)
    agent.chaines={'revision':c}
    return agent,c,g,a


def test_question_resolue_apres_observation_pas_decision(monde):
    agent,c,g,a=preparer(monde)
    assert not hasattr(agent,'sondes_revision_resolues')  # ancien snapshot
    d=agent._sonder_revision([1])
    assert d and d['actions']==[1]
    assert not getattr(agent,'sondes_revision_resolues',set())
    assert agent._sonder_revision([1])['question_revision']==d['question_revision']
    agent.observer(1,g[12],[g[12].tolist()],'continue',source='trace')
    assert d['question_revision'] in agent.sondes_revision_resolues
    assert agent._sonder_revision([1]) is None  # HUD a changé au coup12.
    restore=pickle.loads(pickle.dumps(agent))
    assert restore._sonder_revision([1]) is None
    assert not c.refute  # le modèle/action restent utilisables
    assert agent._predire(c,('UP',)) is not None


def test_contexte_latent_different_autorise(monde,monkeypatch):
    agent,c,g,a=preparer(monde)
    d=agent._sonder_revision([1])
    agent.observer(1,g[12],[g[12].tolist()],'continue',source='trace')
    assert agent._sonder_revision([1]) is None
    rejouer=c.rejouer
    def contexte_nouveau(*args,**kw):
        rapport,courant=rejouer(*args,**kw)
        if courant:
            courant[0].etat['phase_test']=1
        return rapport,courant
    monkeypatch.setattr(c,'rejouer',contexte_nouveau)
    nouveau=agent._sonder_revision([1])
    assert nouveau and nouveau['question_revision']!=d['question_revision']


def test_predictions_contrastes_font_partie_de_la_question(monde):
    agent,c,g,a=preparer(monde)
    from revision_solidite import predire_contraste
    p=agent._predire(c,('UP',));q=predire_contraste(c,('UP',))
    cle=agent._cle_sonde_revision(c,('UP',),p,q)
    q=copy.deepcopy(q);q['issue']='niveau'
    assert agent._cle_sonde_revision(c,('UP',),p,q)!=cle
