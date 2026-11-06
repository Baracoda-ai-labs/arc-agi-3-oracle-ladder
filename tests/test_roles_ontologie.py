# SPDX-License-Identifier: MIT-0
"""Rôles fermés de l'ontologie (B) et équivalence de la langue unique sur les programmes exacts corrigés (CW-348)."""
import glob
import json
from pathlib import Path

import pytest

from chrysalide.langue import depuis_python, vers_python
from chrysalide.langue.roles import RoleRefuse, roles_ontologie, verifier_roles

TEM = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
PROGRAMMES = sorted(f for f in glob.glob("experiments/T3.1/regles/*.json") if f.split("/")[-1][:4] not in TEM)


def test_liste_fermee_lue():
    r = roles_ontologie()
    assert len(r) >= 12 and r["controle"] == () and r["modificateur"] == ("attribut", "valeur")


def test_descriptions_et_menu():
    from chrysalide.langue.roles import descriptions_roles, menu_roles
    assert set(descriptions_roles()) == set(roles_ontologie())  # une description par rôle, ni plus ni moins
    m = menu_roles(["controle", "modificateur"])
    assert m.count("\n") == 1 and "modificateur(attribut, valeur)" in m and "Test :" in m


def test_roles_acceptes():
    assert verifier_roles({"controle": "confirme", ("modificateur", "couleur", 3): "compatible",
                           ("autonome", "rejoue"): "propose"})


@pytest.mark.parametrize("roles", [{"joueur": "confirme"}, {"controle": "vrai"}, {"controle": None},
                                   {("modificateur", "couleur"): "compatible"}, {("solide", 1): "confirme"}, ["controle"]])
def test_roles_refuses(roles):
    with pytest.raises(RoleRefuse):
        verifier_roles(roles)


@pytest.mark.parametrize("f", PROGRAMMES, ids=lambda f: f.split("/")[-1])
def test_ecriture_canonique_stable(f):
    """Côté Python aussi : réécrire le texte lu redonne le même texte (aucune dérive au fil des allers-retours)."""
    t = vers_python(json.loads(Path(f).read_text()))
    assert vers_python(depuis_python(t)) == t


@pytest.mark.parametrize("f", [f for f in PROGRAMMES if "CW-324 P2" in Path(f).read_text()], ids=lambda f: f.split("/")[-1])
def test_budget_P2_traverse_la_langue(f):
    """Le budget de coups et sa défaite (CW-324 P2) survivent à la traduction : règle, remise au début, section niveau."""
    p = depuis_python(vers_python(json.loads(Path(f).read_text())))
    assert any("CW-324 P2" in r.get("nom", "") for r in p["regles"])
    assert ["poser", "budget_restant", ["param", "budget_coups"]] in p.get("au_debut", [])
    assert "budget_coups" in p["niveau"]["*"]
