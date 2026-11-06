"""Simulateur compilé (sim_rapide) : images identiques bit à bit à l'interpréteur (langage.py) sur les parties R0 rejouées."""
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from chrysalide.arc3.langage import ErreurLangage, Programme
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner, image

BANC = Path(__file__).resolve().parents[1] / "experiments/T3.1/bench_sim_rapide.py"
_spec = importlib.util.spec_from_file_location("bench_sim_rapide", BANC)
banc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(banc)
TRACES = banc.charger_traces() if banc.TRACES.exists() else {}

# Toute la suite de l'interpréteur (tests/test_langage.py) rejouée avec ProgrammeCompile à la place de Programme :
# mêmes valeurs, mêmes erreurs, mêmes conflits du mode « lois », mêmes refus de mots et fonctions.
_spec_l = importlib.util.spec_from_file_location("test_langage_compile", Path(__file__).with_name("test_langage.py"))
_tl = importlib.util.module_from_spec(_spec_l)
_spec_l.loader.exec_module(_tl)
_tl.Programme = ProgrammeCompile
for _n, _f in list(vars(_tl).items()):
    if _n.startswith("test_") and callable(_f):
        globals()[f"test_compile_{_n[5:]}"] = _f
CENT_POUR_CENT = ["ls20", "sp80", "ar25", "cd82", "dc22", "lf52", "sk48", "re86"]  # 100 % contre le moteur


@pytest.mark.skipif(not TRACES, reason="traces absentes (bench_sim_rapide.py --extraire)")
@pytest.mark.parametrize("jeu", sorted(TRACES) or ["aucun"])
def test_images_identiques(jeu):
    """Pour chaque coup : interprété (sans copie) contre compilé (avec copie `cloner` à chaque coup, comme une recherche) ;
    même image, même issue, même exception éventuelle. Tous les jeux traduits, pas seulement les 100 %."""
    segs = TRACES[jeu]
    _, n, ii = banc.rejouer(jeu, segs, False, True, False, garder=True)
    _, m, ic = banc.rejouer(jeu, segs, True, True, True, garder=True)
    assert n == m > 0
    assert banc.egales(ii, ic)


@pytest.mark.skipif(not TRACES, reason="traces absentes")
def test_au_moins_cinq_jeux_a_100():
    assert len([j for j in CENT_POUR_CENT if j in TRACES]) >= 5


@pytest.mark.skipif(not TRACES, reason="traces absentes")
@pytest.mark.parametrize("jeu", CENT_POUR_CENT)
def test_etat_cache_et_issue(jeu):
    """Au-delà des images : état caché, issue et attributs égaux après chaque coup (copie de l'état comprise)."""
    pi, pc = Programme(banc.regles(jeu)), ProgrammeCompile(banc.regles(jeu))
    for seg in TRACES[jeu]:
        si, sc = banc.scene_de_json(seg["scene"]), banc.scene_de_json(seg["scene"])
        for a in seg["coups"]:
            sc, pc.etat = cloner(sc, pc.etat)
            pi.step(si, tuple(a))
            pc.step(sc, tuple(a))
            assert si.issue == sc.issue
            assert _forme([o.get("attrs") for o in si.sprites]) == _forme([o.get("attrs") for o in sc.sprites])
            assert [(o["x"], o["y"], o["visible"], o["couche"]) for o in si.sprites] == \
                [(o["x"], o["y"], o["visible"], o["couche"]) for o in sc.sprites]
            assert _forme(pi.etat) == _forme(pc.etat)


def _forme(v, p=4):
    """Valeur comparable (tableaux en listes), profondeur bornée (les attributs peuvent pointer des sprites)."""
    if p == 0:
        return "…"
    if isinstance(v, dict):
        return {k: _forme(x, p - 1) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_forme(x, p - 1) for x in v]
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


# ------------------------------------------------------------------ petits cas de sémantique (sans traces)
def _scene():
    return Scene((4, 8), 0, 1, [
        {"tags": ["joueur"], "pixels": [[3, -1], [3, 3]], "x": 1, "y": 1, "couche": 1},
        {"tags": ["mur"], "pixels": [[5]], "x": 0, "y": 1, "couche": 0},
        {"tags": ["mur"], "pixels": [[5, 5]], "x": 2, "y": 0, "couche": 2},
    ])


@pytest.mark.parametrize("terme", [
    ["chevauche", ["premier", ["objets", {"tag": "joueur"}]], ["elem", ["objets", {"tag": "mur"}], 1]],
    ["libre", ["premier", ["objets", {"tag": "joueur"}]], -1, 0, {"tag": "mur"}],
    ["libre", ["premier", ["objets", {"tag": "joueur"}]], 1, -1, {}],
    ["longueur", ["a", 1, 2]], ["longueur", ["objets", {"couleur": 5, "visible": True}]],
    ["existe", "$o", ["objets", {}], [">", ["x", "$o"], 1]], ["filtrer", "$o", ["objets", {}], ["=", ["y", "$o"], 1]],
    ["si", True, 1], ["table", {"1": 7}, ["+", 0, 1], 9], ["suivant", ["liste", 1, 2, 3], 3],
])
def test_termes_egaux(terme):
    prog = {"etat": {"r": None}, "regles": [{"alors": [["poser", "r", terme]]}]}
    pi, pc = Programme(copy.deepcopy(prog)), ProgrammeCompile(copy.deepcopy(prog))
    pi.step(_scene(), ("UP", None, None))
    pc.step(_scene(), ("UP", None, None))
    assert _forme(pi.etat) == _forme(pc.etat)


def test_memes_erreurs():
    for t in (["inconnu", 1], "$absent", ["si", False, 1]):
        prog = {"regles": [{"alors": [["poser", "r", t]]}]}
        for P in (Programme, ProgrammeCompile):
            with pytest.raises((ErreurLangage, IndexError)):
                P(copy.deepcopy(prog)).step(_scene(), ("UP", None, None))


def test_variable_d_une_autre_regle_inconnue():
    prog = {"regles": [{"soit": {"v": 1}, "quand": False, "puis": "continuer"}, {"alors": [["poser", "r", "$v"]]}]}
    for P in (Programme, ProgrammeCompile):
        with pytest.raises(ErreurLangage):
            P(copy.deepcopy(prog)).step(_scene(), ("UP", None, None))


def test_cloner_garde_les_identites():
    sc = _scene()
    etat = {"cible": sc.sprites[0], "pile": [sc.sprites[0], 3]}
    s2, e2 = cloner(sc, etat)
    assert e2["cible"] is s2.sprites[0] and e2["pile"][0] is s2.sprites[0] and e2["cible"] is not sc.sprites[0]
    assert s2.sprites[0]["pixels"] is sc.sprites[0]["pixels"]  # CW-254 : pixels partagés, copiés à l'écriture
    s2.ecrire(s2.sprites[0], 0, 0, 9)  # toute écriture passe par un effet, qui copie d'abord
    s2.recolorer(s2.sprites[0], 9, 8)
    assert sc.sprites[0]["pixels"][0, 0] == 3 and s2.sprites[0]["pixels"][0, 0] == 8


def test_image_identique_cas_limites():
    sc = _scene()
    sc.sprites[0]["x"] = -1  # sprite à moitié hors vue
    sc.creer({"pixels": [[40000, 2]], "couche": 1, "visible": True}, 6, 3)  # int64 -> int16 comme rendre
    assert np.array_equal(image(sc), sc.image())


def test_cloner_copie_les_canevas():
    from chrysalide.arc3.ontologie_exec import nouveau_canevas
    from chrysalide.arc3.sim_rapide import image_complete
    sc = Scene((8, 8), 0, 1, [], canevas=[nouveau_canevas("i", [[1, 2]], x=3, y=3, kx=2)])
    n, e = cloner(sc, {"c": sc.canevas[0]})
    n.canevas[0]["pixels"][0, 0] = 5
    assert sc.canevas[0]["pixels"][0, 0] == 1 and e["c"] is n.canevas[0]  # copie, identité gardée dans l'état
    assert np.array_equal(image_complete(sc), sc.image_complete()) and image_complete(n)[3, 3] == 5
