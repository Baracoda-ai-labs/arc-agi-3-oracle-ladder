"""Un contre-exemple contextuel doit être respecté dans la recherche."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'paquet'))

from chrysalide.arc3.logique.plan import planifier
from chrysalide.arc3.logique.theorie import Theorie


def test_decor_necessaire_au_blocage(monkeypatch):
    th = Theorie(moves={(1, 4): (1, 0)}, but=('sortie', 1, 9))
    monde = ((1, frozenset({(0, 0)}), 0, 0), (9, frozenset({(0, 0)}), 1, 0))
    th.sans_effet = frozenset({th.cle_sans_effet(monde, 4, (4, 4))})
    assert th.pas(monde, 4, (4, 4))[0] == monde
    monkeypatch.setenv('CHRYS_PLAN_CONTEXTE_COMPLET', '1')
    suite, _ = planifier(th, monde, (4, 4), [4], profondeur=2)
    assert suite is None


def test_mouvement_non_bloque_reste_planifiable(monkeypatch):
    th = Theorie(moves={(1, 4): (1, 0)}, but=('sortie', 1, 9))
    monde = ((1, frozenset({(0, 0)}), 0, 0), (9, frozenset({(0, 0)}), 1, 0))
    monkeypatch.setenv('CHRYS_PLAN_CONTEXTE_COMPLET', '1')
    assert planifier(th, monde, (4, 4), [4], profondeur=2)[0] == [4]
