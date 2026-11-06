"""Garde-fous de la reprise v1, sans charger de jeu ni le paquet de soumission."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def module(monkeypatch):
    paquet = ModuleType('_test_reparation')
    paquet.__path__ = []
    base = ModuleType('_test_reparation.releve_moteur')
    base.FENETRE, base._lot, base._vers_p1 = 40, None, None
    monkeypatch.setitem(sys.modules, paquet.__name__, paquet)
    monkeypatch.setitem(sys.modules, base.__name__, base)
    spec = importlib.util.spec_from_file_location('_test_reparation.reparation_blocage', Path(__file__).parent / 'code/reparation_blocage.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('bloque,epuise,rows,attendu', [(True, False, 41, 2), (False, False, 41, 1),
                                                     (True, True, 41, 1), (True, False, 150, 1)])
def test_reprise_bornee_et_budget_partage(module, monkeypatch, bloque, epuise, rows, attendu):
    horloge = iter([0, 31 if epuise else 1, 2])
    monkeypatch.setattr(module.time, 'process_time', lambda: next(horloge))
    monkeypatch.setenv('CHRYS_P1_MOTEUR_CPU', '30')
    appels = []

    def essai(ex, mode, deadline, reprise):
        appels.append((deadline, reprise))
        return None, bloque

    monkeypatch.setattr(module, '_essai', essai)
    ex = SimpleNamespace(lab=SimpleNamespace(rows=[{'action': 2}] * rows, level=1),
                         j=SimpleNamespace(ecrire=lambda *args, **kwargs: None))
    assert module.tenter(ex, 'joue') is None
    assert len(appels) == attendu
    assert all(deadline == 30 for deadline, _ in appels)
    assert [r for _, r in appels] == list(range(attendu))
