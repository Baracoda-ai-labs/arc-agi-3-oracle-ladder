"""Contrat de connaissance des commandes, sans SDK ni traces de jeu."""
import pickle
from types import SimpleNamespace
import numpy as np
import pytest
from chaine_agent_integree import AgentIntegre
from modele_jeu import ModeleJeu


def agent():
    return AgentIntegre([np.zeros((8,8), dtype=int)], [], [], [], couverture_commandes=True)


def installer(a, m, monkeypatch):
    monkeypatch.setattr('transfert_empreintes.lier', lambda acquis, image: {})
    a.installer_modele_jeu(m)


def test_connues_non_reprobees_commande_nouvelle_reste(monkeypatch):
    a=agent(); m=ModeleJeu('empreintes', {}, {}, commandes_observees={1,2,3,4})
    installer(a,m,monkeypatch)
    assert a.decider([1,2,3,4,5])['actions']==[5]
    assert a.actions==[]


def test_loi_inferee_et_attente_non_observees(monkeypatch):
    a=agent(); a.actions=[1]; a.commandes_connues={2}
    a.attente={'actions':[5]}
    a.chaines['c']=SimpleNamespace(perception={'mouvements':{4:(1,0)}},programme='regle')
    monkeypatch.setattr('diagnostic_contexte_transfert.contexte_source',lambda images:{})
    m=a.consolider_modele_jeu('c', {})
    assert m.commandes_observees=={1,2}
    b=agent(); m.famille='empreintes'
    installer(b,m,monkeypatch)
    assert b.decider([1,2,4,5])['actions']==[4]


def test_installation_refusee_ne_change_pas_commandes():
    a=agent(); a.commandes_connues={2}
    m=ModeleJeu('inconnue',{}, {}, commandes_observees={1})
    with pytest.raises(ValueError): a.installer_modele_jeu(m)
    assert a.commandes_connues=={2}


def test_ancien_pickle_sans_champ(monkeypatch):
    m=ModeleJeu('empreintes',{},{}); del m.commandes_observees
    m=pickle.loads(pickle.dumps(m))
    a=agent(); a.commandes_connues={3}
    installer(a,m,monkeypatch)
    assert a.commandes_connues=={3}


def test_consolidation_installation_ne_modifie_pas_acquis(monkeypatch):
    a=agent(); a.actions=[1,('MOUSE',2,3)]; a.commandes_connues={3}
    vue={'formes':[(1,2)],'but':'egalite'}; programme={'loi':'stable'}
    a.chaines['c']=SimpleNamespace(perception=vue,programme=programme)
    monkeypatch.setattr('diagnostic_contexte_transfert.contexte_source',lambda images:{})
    m=a.consolider_modele_jeu('c',{'preuve':'trace'}); m.famille='empreintes'
    avant=pickle.dumps(m); b=agent(); image=b.images[0].copy()
    installer(b,m,monkeypatch)
    assert b.commandes_connues=={1,3} and b.actions==[]
    assert np.array_equal(b.images[0],image) and pickle.dumps(m)==avant
    assert m.acquis==(vue,programme) and b.memoire_jeu is m
