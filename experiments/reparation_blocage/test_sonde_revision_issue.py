"""Contre-exemples de décision, sans moteur SDK : même image, issues distinctes."""
from types import SimpleNamespace
import pytest
from chaine_agent_integree import AgentIntegre
import revision_solidite


def agent(monkeypatch, nouvelle, ancienne):
    a = AgentIntegre.__new__(AgentIntegre)
    a.chaines = {'repare': SimpleNamespace(contraste_revision={})}
    a.journal = []
    a.attente = None
    a._predire = lambda c, action: {'image': [[0]], 'issue': nouvelle}
    monkeypatch.setattr(revision_solidite, 'predire_contraste',
                        lambda c, action: {'image': [[0]], 'issue': ancienne})
    a._cle_sonde_revision = lambda *args: 'question'
    a._suivre_experience = lambda result: None
    a.dossier = lambda offre: SimpleNamespace(reserve=3, coups_payes=0,
                                             signature=lambda: 'prefixe')
    return a


def test_meme_image_issues_distinctes_fournit_question(monkeypatch):
    a = agent(monkeypatch, 'niveau', None)
    r = a._sonder_revision([1])
    assert r['actions'] == [1] and a.attente is r
    predictions = r['diagnostic']['choix']['predictions']
    assert predictions['corrige']['issue'] == 'niveau'
    assert predictions['ancienne_loi_refutee']['issue'] == 'continue'
    assert predictions['corrige']['image'] == predictions['ancienne_loi_refutee']['image']


@pytest.mark.parametrize('nouvelle,ancienne', [(None, 'continue'), (None, None), ('niveau', 'niveau')])
def test_images_et_issues_equivalentes_ne_depense_pas_sonde(monkeypatch, nouvelle, ancienne):
    a = agent(monkeypatch, nouvelle, ancienne)
    assert a._sonder_revision([1]) is None
    assert a.attente is None


def test_defaite_du_modele_repare_reste_exclue(monkeypatch):
    a = agent(monkeypatch, 'defaite', None)
    assert a._sonder_revision([1]) is None
    assert a.attente is None
