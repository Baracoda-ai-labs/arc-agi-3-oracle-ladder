# SPDX-License-Identifier: MIT-0
"""demander_qwen sans serveur (faux `_appel`) : schéma fermé, abstention, sortie tronquée, plafonds, cache, drapeau éteint."""
import json

import pytest

import chrysalide.qwen.demander as D

DOS = {"menu": {"pousser": {}, "collecte": {}}, "scene": [{"id": "o1"}, {"id": "o2"}]}


@pytest.fixture(autouse=True)
def propre(monkeypatch):
    D._CACHE.clear()
    D._COMPTES.clear()
    D._COMPTES["global"] = 0
    monkeypatch.delenv("CHRYS_QWEN", raising=False)


def faux(rep, fin="stop"):
    return lambda *a, **k: (json.dumps(rep) if isinstance(rep, dict) else rep, fin, {})


def test_choix_et_langue(monkeypatch):
    monkeypatch.setattr(D, "_appel", faux({"candidat": "pousser", "objets": ["o2"], "experience": "pousser contre un mur"}))
    r = D.demander_qwen("regle", DOS, jeu="j", journal=None)
    assert r["statut"] == "propose" and r["choix"]["cle"] == "pousser" and r["langue"].startswith("REPONSE = Choix(")


@pytest.mark.parametrize("rep,statut", [
    ({"candidat": "insuffisant", "objets": [], "experience": ""}, "abstention"),
    ({"candidat": "voler", "objets": [], "experience": ""}, "illisible"),
    ({"candidat": "pousser", "objets": ["o9"], "experience": ""}, "propose"),  # identifiant hors scène : la vérification le refusera
    ("pas du JSON", "illisible"),
])
def test_reponses(monkeypatch, rep, statut):
    monkeypatch.setattr(D, "_appel", faux(rep))
    assert D.demander_qwen("regle", DOS, jeu="j", journal=None, cache=False)["statut"] == statut


def test_tronquee_est_abstention(monkeypatch):
    monkeypatch.setattr(D, "_appel", faux({"candidat": "pousser", "objets": [], "experience": ""}, fin="length"))
    assert D.demander_qwen("regle", DOS, jeu="j", journal=None)["statut"] == "abstention"


def test_plafond_par_jeu_et_cache(monkeypatch):
    n = {"appels": 0}

    def compte(*a, **k):
        n["appels"] += 1
        return json.dumps({"candidat": "collecte", "objets": [], "experience": ""}), "stop", {}
    monkeypatch.setattr(D, "_appel", compte)
    for i in range(6):
        D.demander_qwen("regle", {**DOS, "i": i}, jeu="j", journal=None, plafond_jeu=4)
    assert n["appels"] == 4
    D.demander_qwen("regle", {**DOS, "i": 0}, jeu="k", journal=None)  # même dossier : cache, pas d'appel
    assert n["appels"] == 4


def test_drapeau_eteint_par_defaut():
    assert D.actif() is False
