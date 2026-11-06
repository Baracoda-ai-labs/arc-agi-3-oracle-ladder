# SPDX-License-Identifier: MIT-0
"""Langue unique (docs/LANGUE_PYTHON.md) : aller-retour identique sur les programmes exacts ; refus de la liste blanche."""
import glob
import json

import pytest

from chrysalide.langue import Refus, depuis_python, vers_python

PROGRAMMES = sorted(glob.glob("experiments/T3.1/regles/*.json"))


@pytest.mark.parametrize("f", PROGRAMMES, ids=lambda f: f.split("/")[-1])
def test_aller_retour_identique(f):
    p = json.load(open(f))
    assert depuis_python(vers_python(p)) == p


def test_au_moins_21_programmes():
    assert len(PROGRAMMES) >= 21


ENTETE = "from chrysalide_langue import *\n"


def _prog(regle):
    return ENTETE + f"PROGRAMME = Programme(etat={{}}, regles=[{regle}])\n"


@pytest.mark.parametrize("texte,motif", [
    ("import os\n" + _prog('Regle("r", quand=True, alors=[])'), "affectations"),
    (_prog('Regle("r", quand=o.x == 1, alors=[])'), "liste blanche"),
    (_prog('Regle("r", quand=L[0] == 1, alors=[])'), "liste blanche"),
    (_prog('Regle("r", quand=(lambda: 1)() == 1, alors=[])'), "attribut"),
    (_prog('Regle("r", quand=1 < 2 < 3, alors=[])'), "chaînée"),
    (_prog('Regle("r", quand=exec("x"), alors=[])'), "mot inconnu"),
    (_prog('Regle("r", quand=a is None, alors=[])'), "interdite"),
    (_prog('Regle("r", quand=2 ** 3, alors=[])'), "opérateur"),
    (_prog('Regle("r", quand=True, alors=[gagner()], couleur=3)'), "inconnu de Regle"),
    (ENTETE + "def f():\n    pass\nPROGRAMME = Programme(regles=[])\n", "affectations"),
    (ENTETE + 'PROGRAMME = Programme(origine="induit", regles=[Regle("r", quand=existe(o for o in objets(tag="x")), '
     'alors=[])])\n', "tag"),
])
def test_refus(texte, motif):
    with pytest.raises(Refus, match=motif):
        depuis_python(texte)


def test_sucre_et_constantes():
    t = ENTETE + ('MUR = Classe(couleur=5, roles={"solide": "confirme"})\n'
                  'PROGRAMME = Programme(regles=[Regle("r", soit={"j": premier(objets(couleur=9))}, '
                  'quand=existe(chevauche(j, m) for m in objets(MUR)) and not (action() == "UP"), '
                  'alors=[pour(m, objets(MUR), [deplacer(m, -1, 0)]), si_alors(x(j) >= 3, [gagner()], [])])])\n')
    r = depuis_python(t)["regles"][0]
    assert r["quand"] == ["et", ["existe", "$m", ["objets", {"couleur": 5}], ["chevauche", "$j", "$m"]],
                          ["non", ["=", ["action"], "UP"]]]
    assert r["alors"][0] == ["pour", "$m", ["objets", {"couleur": 5}], [["deplacer", "$m", -1, 0]]]
    assert r["alors"][1] == ["si_alors", [">=", ["x", "$j"], 3], [["gagner"]], []]
