import copy
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import perception_echelles as pe
from chaine_agent_integree import lots, canon
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.plan_langage import cle_complete


def test_prefixe_et_suffixe_sans_reinduction():
    r = Path(__file__).parent / 'runs/sp80_memoire_episodes1/N1'
    g = np.load(r / 'partie.npz')['images']
    actions = json.loads((r / 'partie.json').read_text())['actions']
    h = {'grilles': g[:9].tolist(), 'lots': lots(actions[:8])}
    original = copy.deepcopy(h)
    candidats, rapport = pe.proposer(h)
    assert h == original
    assert not rapport['candidats'][0]['admis']
    assert len(candidats) == 1
    c = candidats[0][1]
    assert c.perception.th_releve.but is None
    assert c.rejouer()[0]['transitions'] == 8
    _, (pc, sc) = c.rejouer()
    pi = Programme(c.programme)
    pi.etat = copy.deepcopy(pc.etat)
    si = copy.deepcopy(sc)
    ecarts = []
    for i in range(8, 11):
        a = canon(actions[i])
        pc.step(sc, a)
        pi.step(si, a)
        assert cle_complete(si, pi.etat) == cle_complete(sc, pc.etat)
        ecarts.append(int(np.sum(c.perception.rendu(sc) != c.perception.vue(g[i + 1]))))
    assert ecarts[:2] == [0, 0]
    assert ecarts[2] > 0  # Une projection corrigée ne prouve pas toute la dynamique.
    assert len(c.grilles) == 9


def test_default_admis_ne_cherche_pas_alternatives(monkeypatch):
    c = SimpleNamespace(perception=SimpleNamespace(tr=SimpleNamespace(s=3, ox=0, oy=0)))
    monkeypatch.setattr(pe, 'construire', lambda *a, **kw: (c, {'admis': True}))
    def interdit(*args):
        raise AssertionError('alternative inutile')
    monkeypatch.setattr(pe, 'echelle_candidats', interdit)
    cs, r = pe.proposer({})
    assert cs == [('legacy', c)] and len(r['candidats']) == 1


def test_budget_nul_aucune_induction(monkeypatch):
    def interdit(*args, **kw):
        raise AssertionError('budget nul')
    monkeypatch.setattr(pe, 'construire', interdit)
    cs, r = pe.proposer({}, secondes=0)
    assert cs == [] and r['budget_epuise']


def test_alternatives_dedoublonnees_et_refusees(monkeypatch):
    calls = []
    def construire(h, limite_s, echelle):
        calls.append(echelle)
        s, x, y = echelle or (7, 0, 0)
        return SimpleNamespace(perception=SimpleNamespace(tr=SimpleNamespace(s=s, ox=x, oy=y))), {'admis': False}
    monkeypatch.setattr(pe, 'construire', construire)
    monkeypatch.setattr(pe, 'echelle_candidats', lambda g: [(7,0,0),(4,0,0),(4,0,0)])
    cs, r = pe.proposer({'grilles': []})
    assert calls == [None, (4,0,0)] and cs == [] and r['admis'] == 0
