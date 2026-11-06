import numpy as np
from chaine_agent_integree import AgentIntegre

def test_commande_offerte_ignoree_prioritaire_sans_nom_de_jeu():
    im=np.zeros((64,64),dtype=int)
    a=AgentIntegre([im]*9,[1,2,3,4]*2,[[im]]*8,['continue']*8,couverture_commandes=True)
    d=a.decider([1,2,3,4,5],secondes=1)
    assert d['actions']==[5] and d['origine']=='commande_offerte_non_testee'
    a.observer(5,im,[im],'continue')
    assert 5 in a.actions
    assert a.attente is None

def test_aucune_action_non_offerte_ou_reset():
    im=np.zeros((64,64),dtype=int)
    a=AgentIntegre([im],[],[],[],couverture_commandes=True)
    d=a.decider([0,7],secondes=1)
    assert d['actions']==[7]

def test_changement_commande_reteste_actions_sans_affirmer_selection():
    im=np.zeros((64,64),dtype=int)
    a=AgentIntegre([im]*9,[1,2,3,4]*2,[[im]]*8,['continue']*8,couverture_commandes=True)
    assert a.decider([1,2,3,4,5])['actions']==[5]
    change=im.copy();change[20,20]=1
    a.observer(5,change,[change],'continue')
    for action in [1,2,3,4]:
        d=a.decider([1,2,3,4,5])
        assert d['actions']==[action] and d['statut']=='experience_contexte_commande'
        a.observer(action,change,[change],'continue')
    assert not a.sondes_contexte
