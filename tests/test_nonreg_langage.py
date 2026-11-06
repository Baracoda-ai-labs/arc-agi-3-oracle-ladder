import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[1]


def _module(chemin, nom):
    spec = importlib.util.spec_from_file_location(nom, RACINE / chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_drapeau_a_vide():
    pytest.importorskip("arc_agi")
    sys.path.insert(0, str(RACINE / "experiments/T3.1"))
    m = _module("experiments/T3.1/mesure_exhaustivite.py", "mesure_exhaustivite")
    assert m.a_vide(1.0) and m.a_vide(0.99)  # lf52 : le témoin « aucune règle » fait 100 %
    assert not m.a_vide(0.98) and not m.a_vide(0.0)
    assert not m.a_vide(None)  # aucune transition : pas de témoin, pas « à vide » (et pas reproduit non plus)


def test_rang_distracteurs_egalites_pessimistes():
    pytest.importorskip("arc_agi")
    sys.path.insert(0, str(RACINE / "experiments/T3.1"))
    m = _module("experiments/T3.1/mesure_exhaustivite.py", "mesure_exhaustivite")
    assert m.rang(0, [3, 5]) == 1  # prédiction exacte, distracteurs plus loin : premier
    assert m.rang(2, [2, 5]) == 2  # égalité : le distracteur passe devant (pessimiste)
    assert m.rang(0, [0, 0, 0]) == 4  # tout à égalité : dernier
    assert m.rang(float("inf"), [float("inf")]) == 2  # règle plantée : rang le pire
    a, b = np.zeros((2, 2)), np.eye(2)
    assert m.distance(a, b) == 2 and m.distance(a, np.zeros((3, 3))) == 9 and m.distance(None, a) == float("inf")
    d = {"n": 0, "p1": 0, "rang": 0.0, "k": 0, "sans": 0}
    m._classer(d, a, a, [])  # aucun distracteur distinct : exclu, compté à part
    m._classer(d, a, a, [b])  # exact : rang 1
    m._classer(d, a, b, [a])  # la prédiction est le distracteur : rang 2 sur 2, normalisé 1
    assert d == {"n": 2, "p1": 1, "rang": 1.0, "k": 2, "sans": 1}


def test_baisses_detecte_regression():
    nr = _module("scripts/nonreg_langage.py", "nonreg_langage")
    ref = {"ls20": {"exactes_honnetes": 329, "reproduit": True}, "tr87": {"exactes_honnetes": 354, "reproduit": False}}
    assert nr.baisses({"ls20": {"exactes_honnetes": 329, "reproduit": True},
                       "tr87": {"exactes_honnetes": 360, "reproduit": False}}, ref) == []
    b = nr.baisses({"ls20": {"exactes_honnetes": 329, "reproduit": False}}, ref)
    assert len(b) == 2 and "ls20" in b[0] and "tr87" in b[1]


def test_baisses_ignore_reference_a_vide():
    nr = _module("scripts/nonreg_langage.py", "nonreg_langage")
    ref = {"lf52": {"exactes_honnetes": 180, "reproduit": False, "a_vide": True}}
    assert nr.baisses({"lf52": {"exactes_honnetes": 62, "reproduit": False}}, ref) == []  # 180 « à vide » : rien de prouvé
    assert nr.baisses({}, ref) == ["lf52 : absent"]
