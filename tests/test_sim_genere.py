"""[G] Simulateur à code généré (sim_genere) : mêmes résultats que sim_rapide (et donc que l'interpréteur langage.py)."""
import copy
import os
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from chrysalide.arc3 import sim_genere as g
from chrysalide.arc3 import sim_rapide as sr
from chrysalide.arc3.langage import ErreurLangage, Programme
from chrysalide.arc3.logique.plan_langage import cle_complete

ICI = Path(__file__).resolve().parent


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# Toute la suite de l'interpréteur (tests/test_langage.py) rejouée avec ProgrammeGenere à la place de Programme.
_tl = _charger("test_langage_genere", ICI / "test_langage.py")
_tl.Programme = g.ProgrammeGenere
for _n, _f in list(vars(_tl).items()):
    if _n.startswith("test_") and callable(_f):
        globals()[f"test_genere_{_n[5:]}"] = _f

# Les petits cas de test_sim_rapide, avec ProgrammeGenere et la copie de G.
_tr = _charger("test_sim_rapide_genere", ICI / "test_sim_rapide.py")
_scene, _forme, banc = _tr._scene, _tr._forme, _tr.banc
TRACES = _tr.TRACES


@pytest.mark.parametrize("terme", [
    ["chevauche", ["premier", ["objets", {"tag": "joueur"}]], ["elem", ["objets", {"tag": "mur"}], 1]],
    ["libre", ["premier", ["objets", {"tag": "joueur"}]], -1, 0, {"tag": "mur"}],
    ["longueur", ["a", 1, 2]], ["longueur", ["objets", {"couleur": 5, "visible": True}]],
    ["existe", "$o", ["objets", {}], [">", ["x", "$o"], 1]], ["filtrer", "$o", ["objets", {}], ["=", ["y", "$o"], 1]],
    ["si", True, 1], ["table", {"1": 7}, ["+", 0, 1], 9], ["suivant", ["liste", 1, 2, 3], 3],
    ["argmin", "$o", ["objets", {}], ["-", 0, ["x", "$o"]]],
    ["tous", "$o", ["objets", {}], ["<", ["y", "$o"], ["longueur", ["objets", {"tag": "mur"}]]]],  # sortie de boucle
    ["existe", "$i", ["intervalle", 0, 4], ["=", ["pixel", ["premier", ["objets", {"tag": "joueur"}]], ["%", "$i", 2],
                                                ["//", "$i", 2]], -1]],
    ["filtrer", "$o", ["objets", {}], ["a_tag", "$o", "mur"]], ["premier_tel_que", "$o", ["liste"], True],
])
def test_termes_egaux(terme):
    prog = {"etat": {"r": None}, "regles": [{"alors": [["poser", "r", terme]]}]}
    pi, pg = Programme(copy.deepcopy(prog)), g.ProgrammeGenere(copy.deepcopy(prog))
    pi.step(_scene(), ("UP", None, None))
    pg.step(_scene(), ("UP", None, None))
    assert _forme(pi.etat) == _forme(pg.etat)


def test_sortie_de_boucle_paresseuse():
    """Liste vide : le sous-terme sorti de boucle n'est jamais évalué (pas d'erreur), comme sim_rapide ; non vide : la même
    erreur, au même moment."""
    vide = {"regles": [{"alors": [["poser", "r", ["tous", "$o", ["liste"], ["=", ["x", ["elem", ["liste"], 3]], 1]]]]}]}
    for P in (sr.ProgrammeCompile, g.ProgrammeGenere):
        p = P(copy.deepcopy(vide))
        p.step(_scene(), ("UP", None, None))
        assert p.etat["r"] is True
    plein = copy.deepcopy(vide)
    plein["regles"][0]["alors"][0][2][2] = ["objets", {}]
    for P in (sr.ProgrammeCompile, g.ProgrammeGenere):
        with pytest.raises(IndexError):
            P(copy.deepcopy(plein)).step(_scene(), ("UP", None, None))


def test_effets_egaux():
    prog = {"etat": {"n": 0, "pile": []}, "mots": {"pas": {"sorte": "effet", "params": ["$o"],
                                                            "corps": [["deplacer", "$o", 1, 0]]}},
            "regles": [{"alors": [["pour", "$o", ["objets", {"tag": "mur"}], [["pas", "$o"], ["consommer", "n", 1]]],
                                  ["si_alors", [">", ["etat", "n"], -5], [["empiler", "pile", ["etat", "n"]]],
                                   [["poser", "n", 0]]],
                                  ["poser_attr", ["premier", ["objets", {"tag": "joueur"}]], "k", ["liste", 1]],
                                  ["montrer", ["premier", ["objets", {"tag": "joueur"}]], False], ["depiler", "pile"],
                                  ["poser", "d", "$_depile"]]}]}
    si, sg = _scene(), _scene()
    pi, pg = Programme(copy.deepcopy(prog)), g.ProgrammeGenere(copy.deepcopy(prog))
    pi.step(si, ("UP", None, None))
    pg.step(sg, ("UP", None, None))
    assert _forme(pi.etat) == _forme(pg.etat) and np.array_equal(si.image(), sr.image(sg))
    assert _forme([o.get("attrs") for o in si.sprites]) == _forme([o.get("attrs") for o in sg.sprites])


def test_memes_erreurs():
    for t in (["inconnu", 1], "$absent", ["si", False, 1]):
        prog = {"regles": [{"alors": [["poser", "r", t]]}]}
        with pytest.raises((ErreurLangage, IndexError)):
            g.ProgrammeGenere(copy.deepcopy(prog)).step(_scene(), ("UP", None, None))


def test_cloner_et_cle():
    sc = _scene()
    sc.sprites[0]["cache"] = {"rotation": 0}
    etat = {"cible": sc.sprites[0], "pile": [sc.sprites[0], 3], "c": sc.sprites[0]["cache"], "l": [[1, 2], [3]]}
    a, b = sr.cloner(sc, etat), g.cloner(sc, etat)
    s2, e2 = b
    assert e2["cible"] is s2.sprites[0] and e2["pile"][0] is s2.sprites[0] and e2["cible"] is not sc.sprites[0]
    assert e2["c"] is s2.sprites[0]["cache"] and e2["c"] is not sc.sprites[0]["cache"]
    assert e2["l"] == etat["l"] and e2["l"][0] is not etat["l"][0]
    assert s2.sprites[0]["pixels"] is sc.sprites[0]["pixels"]
    assert cle_complete(*a) == cle_complete(*b) == g.cle_complete(*b) == g.cle_complete(sc, etat)
    assert g.cle_plate(*a) == g.cle_plate(*b) == g.cle_plate(sc, etat)
    s2.sprites[1]["x"] += 1  # un champ change : les deux clés changent
    assert g.cle_plate(*b) != g.cle_plate(sc, etat) and g.cle_complete(*b) != g.cle_complete(sc, etat)
    s2.sprites[1]["x"] -= 1
    s2.sprites[0], s2.sprites[1] = s2.sprites[1], s2.sprites[0]  # ordre des sprites : même classe
    assert g.cle_plate(*b) == g.cle_plate(sc, etat)


@pytest.mark.skipif(not TRACES, reason="traces absentes (bench_sim_rapide.py --extraire)")
@pytest.mark.parametrize("jeu", sorted(TRACES) or ["aucun"])
def test_traces_identiques(jeu):
    """Chaque coup des traces : même exception, issue, image et clé que sim_rapide (copie à chaque coup)."""
    banc_g = _charger("banc_traces_g", ICI.parent / "experiments/G/banc_traces.py")
    n, ecarts, premier = banc_g.controle(jeu, TRACES[jeu])
    assert n > 0 and ecarts == 0, premier


def test_interrupteur():
    assert g.ACTIF == (os.environ.get("CHRYS_BACKEND_TABLEAUX", "1") in ("1", "2"))  # allumé par défaut (CW-304)
    fait = g.installer(force=True)
    try:
        assert sr.ProgrammeCompile is g.ProgrammeGenere and sr.cloner is g.cloner and ("chrysalide.arc3.sim_rapide", "cloner") in fait
    finally:
        g.desinstaller()
    assert sr.ProgrammeCompile is not g.ProgrammeGenere and sr.cloner is not g.cloner
    import chrysalide.arc3.logique.plan_langage as pl
    orig = pl.cle_complete
    g.installer(force=True, plate=True)
    try:
        assert pl.cle_complete is g.cle_plate
    finally:
        g.desinstaller()
    assert pl.cle_complete is orig
