"""Langage v0 (T3.2) : un petit jeu de couloir entièrement décrit en règles déclaratives, rejoué contre une vérité codée à part."""
import pytest

from chrysalide.arc3.langage import ErreurLangage, Programme, mots_valides
from chrysalide.arc3.ontologie_exec import Scene

JEU = {
    "etat": {"pas": 0},
    "regles": [
        {"nom": "flèche", "quand": ["contient", ["liste", "UP", "DOWN", "LEFT", "RIGHT"], ["action"]],
         "soit": {"j": ["premier", ["objets", {"tag": "joueur"}]],
                  "dx": ["si", ["=", ["action"], "LEFT"], -1, ["si", ["=", ["action"], "RIGHT"], 1, 0]],
                  "dy": ["si", ["=", ["action"], "UP"], -1, ["si", ["=", ["action"], "DOWN"], 1, 0]]},
         "alors": [["poser", "pas", ["+", ["etat", "pas"], 1]]], "puis": "continuer"},
        {"nom": "déplacement", "quand": ["et", ["contient", ["liste", "LEFT", "RIGHT"], ["action"]],
                                         ["libre", ["premier", ["objets", {"tag": "joueur"}]],
                                          ["si", ["=", ["action"], "LEFT"], -1, 1], 0, {"tag": "mur"}]],
         "soit": {"j": ["premier", ["objets", {"tag": "joueur"}]]},
         "alors": [["deplacer", "$j", ["si", ["=", ["action"], "LEFT"], -1, 1], 0]], "puis": "continuer"},
        {"nom": "sortie", "quand": ["chevauche", ["premier", ["objets", {"tag": "joueur"}]], ["premier", ["objets", {"tag": "porte"}]]],
         "alors": [["niveau_suivant"]]},
        {"nom": "clic recolore", "quand": ["=", ["action"], "CLICK"],
         "soit": {"c": ["case_clic"]},
         "alors": [["pour", "$o", ["a", ["elem", "$c", 0], ["elem", "$c", 1]], [["recolorer", "$o", 5, 6]]]]},
    ],
}


def scene():
    return Scene((4, 8), 0, 1, [
        {"tags": ["joueur"], "pixels": [[3]], "x": 1, "y": 1, "couche": 1},
        {"tags": ["mur"], "pixels": [[5]], "x": 0, "y": 1, "couche": 0},
        {"tags": ["porte"], "pixels": [[9]], "x": 4, "y": 1, "couche": 0},
    ])


def test_regles_declaratives_deplacement_mur_sortie():
    p, sc = Programme(JEU), scene()
    p.step(sc, ("LEFT", None, None))
    assert sc.par_tag("joueur")[0]["x"] == 1 and p.etat["pas"] == 1     # mur à gauche : pas de mouvement
    for _ in range(3):
        p.step(sc, ("RIGHT", None, None))
    assert sc.par_tag("joueur")[0]["x"] == 4 and sc.issue == "niveau" and p.etat["pas"] == 4


def test_clic_vers_case_et_recolorer():
    p, sc = Programme(JEU), scene()
    # vue 8 de large × 4 de haut → échelle 8, bandes verticales de (64-32)//2 = 16 ; la case (0, 1) = pixels 24..31 × 0..7
    p.step(sc, ("CLICK", 25, 3))
    assert sc.par_tag("mur")[0]["pixels"][0][0] == 6


def test_terme_inconnu_refuse():
    p = Programme({"regles": [{"quand": ["teleporte_tout"], "alors": []}]})
    try:
        p.step(scene(), ("UP", None, None))
        raise AssertionError("aurait dû refuser")
    except ErreurLangage:
        pass


def test_termes_v0_1_identite_quantifieurs_pixel_cycle():
    sc = scene()
    j, mur, _porte = sc.sprites
    env = {"_scene": sc, "_action": ("UP", None, None), "j": j, "m": mur}
    p = Programme({"regles": []})
    assert p.ev(["=", "$j", "$j"], env) and not p.ev(["=", "$j", "$m"], env)          # objets : identité, sans planter
    assert p.ev(["contient", ["objets", {}], "$j"], env)
    assert p.ev(["existe", "$o", ["objets", {}], ["=", ["pixel", "$o", 0, 0], 9]], env)
    assert p.ev(["premier_tel_que", "$o", ["objets", {}], ["=", ["pixel", "$o", 0, 0], 5]], env) is mur
    assert not p.ev(["tous", "$o", ["objets", {}], ["=", ["x", "$o"], 1]], env)
    assert p.ev(["suivant", ["liste", "A", "B", "C"], "C"], env) == "A" and p.ev(["vue"], env) == [8, 4]
    assert p.ev(["table", {"1": "un"}, 1], env) == "un"
    sc.niveau = 3
    assert p.ev(["niveau"], env) == 3
    p.fait(["si_alors", ["=", ["niveau"], 3], [["deplacer", "$j", 2, 0]], [["deplacer", "$j", -1, 0]]], env)
    assert j["x"] == 3


def test_tant_que_borne_et_reevaluation():
    sc = scene()
    j = sc.sprites[0]
    env = {"_scene": sc, "_action": ("RIGHT", None, None), "j": j}
    p = Programme({"etat": {"n": 0}, "regles": []})
    # glisse vers la droite tant que la case suivante est libre de la porte (x=4) : s'arrête à x=3, cond réévaluée
    p.fait(["tant_que", ["libre", "$j", 1, 0, {"tag": "porte"}], [["deplacer", "$j", 1, 0]], 10], env)
    assert j["x"] == 3
    p.fait(["tant_que", True, [["poser", "n", ["+", ["etat", "n"], 1]]], 5], env)   # borne explicite
    assert p.etat["n"] == 5
    p.fait(["tant_que", True, [["poser", "n", ["+", ["etat", "n"], 1]]]], env)      # borne par défaut 64
    assert p.etat["n"] == 69
    p.fait(["tant_que", False, [["poser", "n", 0]]], env)                           # cond fausse : aucun passage
    assert p.etat["n"] == 69


def test_intervalle_et_tri():
    sc = scene()
    j, mur, porte = sc.sprites
    env = {"_scene": sc, "_action": ("UP", None, None)}
    p = Programme({"regles": []})
    assert p.ev(["intervalle", 2, 5], env) == [2, 3, 4] and p.ev(["intervalle", 3, 3], env) == []
    assert p.ev(["trier", ["objets", {}], "$o", ["x", "$o"]], env) == [mur, j, porte]
    assert p.ev(["trier_desc", ["objets", {}], "$o", ["x", "$o"]], env) == [porte, j, mur]
    paires = ["liste", ["liste", 1, "a"], ["liste", 0, "b"], ["liste", 1, "c"], ["liste", 0, "d"]]
    assert p.ev(["trier", paires, "$p", ["elem", "$p", 0]], env) == [[0, "b"], [0, "d"], [1, "a"], [1, "c"]]  # stable
    assert p.ev(["trier_desc", paires, "$p", ["elem", "$p", 0]], env) == [[1, "a"], [1, "c"], [0, "b"], [0, "d"]]
    assert p.ev(["trier", ["intervalle", 0, 4], "$i", ["%", "$i", 2]], env) == [0, 2, 1, 3]
def test_soit_creer_lie_le_nouvel_objet():
    sc = scene()
    p = Programme({"regles": [{"soit": {"m": ["premier", ["objets", {"tag": "porte"}]]},
                               "alors": [["soit_creer", "$n", "$m", 6, 2,
                                          [["poser_attr", "$n", "role", "copie"], ["recolorer", "$n", 9, 4]]]]}]})
    p.step(sc, ("UP", None, None))
    porte, copie = sc.par_tag("porte")
    assert (copie["x"], copie["y"], copie["attrs"], int(copie["pixels"][0][0])) == (6, 2, {"role": "copie"}, 4)
    assert "attrs" not in porte and int(porte["pixels"][0][0]) == 9 and copie["visible"]   # modèle intact
    sc.image()


def test_accesseurs_visible_calque_tag_bloquant():
    sc = scene()
    j, mur, porte = sc.sprites
    mur["bloquant"] = True
    porte["bloquant"] = False
    sc.montrer(porte, False)
    env = {"_scene": sc, "_action": ("UP", None, None), "j": j, "m": mur, "p": porte, "rien": None}
    p = Programme({"regles": []})
    assert p.ev(["visible", "$j"], env) and not p.ev(["visible", "$p"], env)
    assert p.ev(["calque", "$j"], env) == 1 and p.ev(["calque", "$m"], env) == 0
    assert p.ev(["a_tag", "$m", "mur"], env) and not p.ev(["a_tag", "$m", "joueur"], env)
    assert p.ev(["bloquant", "$m"], env) and not p.ev(["bloquant", "$p"], env) and p.ev(["bloquant", "$j"], env)  # défaut moteur
    assert not p.ev(["a_tag", "$rien", "mur"], env) and p.ev(["calque", "$rien"], env) is None
    p.fait(["calque", "$j", 5], env)                                                  # l'effet à 2 arguments reste un effet
    assert p.ev(["calque", "$j"], env) == 5
    try:
        p.ev(["calque", "$j", 2], env)
        raise AssertionError("aurait dû refuser")
    except ErreurLangage:
        pass


def test_debut_niveau_et_au_debut():
    prog = {"etat": {"init": 0, "vus": 0},
            "au_debut": [["poser", "init", ["+", ["etat", "init"], 1]]],
            "regles": [{"quand": ["debut_niveau"], "alors": [["poser", "vus", ["+", ["etat", "vus"], 1]]]}]}
    p, sc = Programme(prog), scene()
    for _ in range(3):
        p.step(sc, ("UP", None, None))
    assert p.etat == {"init": 1, "vus": 1}            # une seule fois par scène
    sc2 = scene()                                      # scène neuve (niveau suivant / RESET)
    p.step(sc2, ("UP", None, None))
    assert p.etat == {"init": 2, "vus": 2}
    sc3 = scene()
    sc3.debut = False                                  # resynchronisation en cours de niveau (banc) : pas un début
    p.step(sc3, ("UP", None, None))
    assert p.etat == {"init": 2, "vus": 2}


def test_refleter_axe_x_et_y():
    sc = Scene((8, 8), 0, 1, [{"tags": ["c"], "pixels": [[1, 2]], "x": 1, "y": 3, "couche": 0}])
    env = {"_scene": sc, "_action": ("CLICK", None, None)}
    p = Programme({"regles": []})
    p.fait(["refleter", ["objets", {"tag": "c"}], "x", 4], env)
    m = sc.sprites[-1]
    assert (m["x"], m["y"], m["pixels"].tolist()) == (5, 3, [[2, 1]])
    p.fait(["refleter", sc.sprites[0], "y", 4], env)
    m = sc.sprites[-1]
    assert (m["x"], m["y"]) == (1, 4) and len(sc.sprites) == 3


def _env(sc):
    return {"_scene": sc, "_action": ("UP", None, None)}


def test_v0_2_calcul_reel_et_alea():
    import random

    p, env = Programme({"regles": []}), _env(scene())
    assert p.ev(["div", 7, 2], env) == 3.5 and p.ev(["racine", 16], env) == 4.0
    assert p.ev(["arrondi", 2.5], env) == 2 and p.ev(["arrondi", 3.5], env) == 4      # round de Python (moitié → pair)
    assert p.ev(["plancher", -0.5], env) == -1
    r = random.Random(4)
    attendu = [r.choice([0, 90, 180, 270]) for _ in range(6)]                       # comme tr87.on_set_level
    assert [90 * p.ev(["alea", 4, 4, k], env) for k in range(6)] == attendu
    r.seed(7)
    assert [p.ev(["alea", 7, 7, k], env) for k in range(5)] == [r.randint(0, 6) for _ in range(5)]


def test_v0_2_composantes_union_find():
    sc = Scene((8, 8), 0, 1, [{"pixels": [[1, 1]], "x": x, "y": 0, "couche": 0} for x in (0, 1, 5, 2)])
    p = Programme({"regles": []})
    g = p.ev(["composantes", "$a", "$b", ["objets", {}], ["chevauche", "$a", "$b"]], _env(sc))
    assert [[o["x"] for o in c] for c in g] == [[0, 1, 2], [5]]


def test_v0_2_contact_moteur_compte_les_moins_deux():
    sc = Scene((4, 4), 0, 1, [{"pixels": [[-2, 3]], "x": 0, "y": 0, "couche": 0},
                              {"pixels": [[4]], "x": 0, "y": 0, "couche": 0}])
    a, b = sc.sprites
    env, p = {**_env(sc), "a": a, "b": b}, Programme({"regles": []})
    assert not p.ev(["chevauche", "$a", "$b"], env) and p.ev(["contact_moteur", "$a", "$b"], env)
    b["bloquant"] = False
    assert not p.ev(["contact_moteur", "$a", "$b"], env)


def test_v0_2_contact_et_remodeler_identiques_au_moteur():
    import numpy as np
    import pytest

    sprites = pytest.importorskip("arcengine").Sprite
    motif = [[1, 2, -1], [3, -2, 5], [-1, 6, 6], [7, 7, 8]]
    for k in (2, 3, 1):
        s = sprites([row[:] for row in motif], x=0, y=0).set_scale(2)
        o = {"pixels": np.asarray(s.render(), dtype=np.int16), "x": 0, "y": 0, "couche": 0, "echelle": 2}
        Scene((1, 1), 0, 0, []).remodeler(o, k)
        assert np.array_equal(o["pixels"], s.set_scale(k).render()), k
    plein = [[1, 1, 2, 2], [1, -1, 2, 3], [-1, -1, 4, 4], [-1, 5, 4, 4]]
    s, o = sprites([row[:] for row in plein]), {"pixels": np.asarray(plein, dtype=np.int16), "x": 0, "y": 0, "couche": 0}
    sc = Scene((1, 1), 0, 0, [])
    sc.remodeler(o, -1)
    assert np.array_equal(o["pixels"], s.set_scale(-1).render())
    sc.remodeler(o, 1)
    assert np.array_equal(o["pixels"], np.asarray(plein))                            # base gardée après réduction
    a, b = sprites([[-2, 3]], x=0, y=0), sprites([[4, 4], [4, -1]], x=-1, y=0)
    da, db = ({"pixels": np.asarray(t.render()), "x": t.x, "y": t.y} for t in (a, b))
    env = {**_env(Scene((1, 1), 0, 0, [])), "a": da, "b": db}
    assert Programme({}).ev(["contact_moteur", "$a", "$b"], env) is a.collides_with(b) is True


def test_v0_2_remodeler_effet_et_rendu():
    sc = Scene((4, 8), 0, 1, [{"pixels": [[3, -1], [3, 3]], "x": 1, "y": 1, "couche": 1}])
    p, o = Programme({"regles": []}), sc.sprites[0]
    p.fait(["remodeler", "$o", 2, 2], {**_env(sc), "o": o})
    assert o["pixels"].shape == (4, 4) and p.ev(["echelle", "$o"], {**_env(sc), "o": o}) == 2
    img = sc.image()                                     # vue 8×4 → 8 px par case, bande de 16 en haut ; objet en (1, 1)
    assert img[16 + 8, 8] == 3 and img[16 + 8, 8 * 3] == 0 and img[16 + 8 * 3, 8 * 3] == 3


def test_v0_2_pousser_en_chaine():
    sc = Scene((1, 10), 0, 1, [{"tags": ["j"], "pixels": [[1]], "x": 0, "y": 0, "couche": 0}]
               + [{"tags": ["c"], "pixels": [[2]], "x": x, "y": 0, "couche": 0} for x in (1, 2)]
               + [{"tags": ["m"], "pixels": [[5]], "x": 9, "y": 0, "couche": 0}])
    p = Programme({"regles": [{"alors": [["pousser", ["premier", ["objets", {"tag": "j"}]], 1, 0, {"tag": "m"}, {"tag": "c"},
                                          "bloque"]]}]})
    p.step(sc, ("RIGHT", None, None))
    assert [o["x"] for o in sc.sprites] == [1, 2, 3, 9] and p.etat["bloque"] is False
    for _ in range(6):
        p.step(sc, ("RIGHT", None, None))
    assert [o["x"] for o in sc.sprites] == [6, 7, 8, 9] and p.etat["bloque"] is True  # chaîne bloquée par le mur


def test_mode_lois_conditions_sur_etat_avant():
    """Deux lois atomiques : en mode séquentiel la 2ᵉ voit l'effet de la 1ʳᵉ ; en mode « lois », non."""
    def jeu(mode):
        return {"mode": mode, "regles": [
            {"quand": ["=", ["x", ["premier", ["objets", {"tag": "a"}]]], 0],
             "alors": [["deplacer", ["premier", ["objets", {"tag": "a"}]], 1, 0]], "puis": "continuer"},
            {"quand": ["=", ["x", ["premier", ["objets", {"tag": "a"}]]], 1],
             "alors": [["deplacer", ["premier", ["objets", {"tag": "b"}]], 0, 1]]}]}
    for mode, yb in (("sequentiel", 1), ("lois", 0)):
        sc = Scene((4, 4), 0, 1, [{"tags": ["a"], "pixels": [[1]], "x": 0, "y": 0, "couche": 0},
                                  {"tags": ["b"], "pixels": [[2]], "x": 3, "y": 0, "couche": 0}])
        Programme(jeu(mode)).step(sc, ("RIGHT", None, None))
        assert sc.sprites[0]["x"] == 1 and sc.sprites[1]["y"] == yb


def test_mode_lois_poids_conflit():
    """Deux lois déplacent le même objet : la plus lourde gagne, l'autre est journalisée ; à poids égal, les deux s'appliquent."""
    def jeu(p1, p2):
        o = ["premier", ["objets", {"tag": "a"}]]
        return {"mode": "lois", "regles": [{"nom": "droite", "poids": p1, "alors": [["deplacer", o, 1, 0]]},
                                           {"nom": "bas", "poids": p2, "alors": [["deplacer", o, 0, 1]]}]}
    for (p1, p2), pos in (((1, 3), (0, 1)), ((3, 1), (1, 0)), ((1, 1), (1, 1))):
        sc = Scene((4, 4), 0, 1, [{"tags": ["a"], "pixels": [[1]], "x": 0, "y": 0, "couche": 0}])
        p = Programme(jeu(p1, p2))
        p.step(sc, ("UP", None, None))
        assert (sc.sprites[0]["x"], sc.sprites[0]["y"]) == pos
        assert len(p.conflits) == (0 if p1 == p2 else 1)


# ------------------------------------------------------------- mots nouveaux (macros) et fonctions pures
def _env(sc):
    return {"_scene": sc, "_action": ("RIGHT", None, None)}


def test_macro_terme_et_effet():
    p = Programme({"mots": {
        "joueur": {"params": [], "corps": ["premier", ["objets", {"tag": "joueur"}]]},
        "dx_de": {"params": ["$a"], "corps": ["si", ["=", "$a", "LEFT"], -1, ["si", ["=", "$a", "RIGHT"], 1, 0]]},
        "avancer": {"params": ["$o", "$d"], "sorte": "effet",
                    "corps": [["si_alors", ["libre", "$o", "$d", 0, {"tag": "mur"}], [["deplacer", "$o", "$d", 0]]]]},
        "tous_droite": {"params": ["$l"], "sorte": "effet", "corps": [["pour", "$e", "$l", [["avancer", "$e", 1]]]]}},
        "regles": [{"soit": {"j": ["joueur"]}, "alors": [["avancer", "$j", ["dx_de", ["action"]]]]}]})
    sc = scene()
    p.step(sc, ("RIGHT", None, None))
    assert sc.par_tag("joueur")[0]["x"] == 2
    p.step(sc, ("LEFT", None, None))
    p.step(sc, ("LEFT", None, None))                     # mur en x=0 : bloqué
    assert sc.par_tag("joueur")[0]["x"] == 1
    p.fait(["tous_droite", ["objets", {"tag": "joueur"}]], _env(sc))
    assert sc.par_tag("joueur")[0]["x"] == 2


@pytest.mark.parametrize("mots, motif", [
    ({"f": {"params": ["$a"], "corps": ["+", "$a", "$b"]}}, "variable"),              # portée lexicale
    ({"x": {"params": [], "corps": 1}}, "natif"),                                      # masque un mot natif
    ({"f": {"params": ["$a"], "corps": ["f", "$a"]}}, "récursion"),
    ({"f": {"params": [], "corps": ["g"]}, "g": {"params": [], "corps": ["f"]}}, "récursion"),
    ({"f": {"params": [], "corps": ["inconnu_zz", 1]}}, "inconnu"),
    ({"f": {"params": ["$a", "$a"], "corps": 1}}, "param"),
    ({"f": {"params": ["$a"], "corps": 1}, "g": {"params": [], "corps": ["f", 1, 2]}}, "arité"),
    ({"f": {"params": [], "corps": 1, "sorte": "autre"}}, "sorte"),
])
def test_macro_refus_a_la_definition(mots, motif):
    with pytest.raises(ErreurLangage, match=motif):
        Programme({"mots": mots})


def test_macro_erreurs_a_l_appel_et_profondeur():
    p = Programme({"mots": {"f": {"params": ["$a"], "corps": "$a"},
                            "e": {"params": [], "sorte": "effet", "corps": [["gagner"]]}}})
    env = _env(scene())
    assert p.ev(["f", ["+", 1, 2]], env) == 3
    with pytest.raises(ErreurLangage, match="arité"):
        p.ev(["f", 1, 2], env)
    with pytest.raises(ErreurLangage, match="effet"):
        p.ev(["e"], env)
    with pytest.raises(ErreurLangage, match="terme"):
        p.fait(["f", 1], env)
    with pytest.raises(ErreurLangage, match="inconnu"):
        p.ev(["g", 1], env)
    chaine = {f"m{i}": {"params": [], "corps": [f"m{i + 1}"]} for i in range(20)} | {"m20": {"params": [], "corps": 7}}
    with pytest.raises(ErreurLangage, match="profondeur"):
        Programme({"mots": chaine}).ev(["m0"], env)
    court = {f"m{i}": {"params": [], "corps": [f"m{i + 1}"]} for i in range(10)} | {"m10": {"params": [], "corps": 7}}
    assert Programme({"mots": court}).ev(["m0"], env) == 7


def test_fonction_pure_calcule():
    p = Programme({"fonctions": {
        "dist": {"params": ["a", "b"], "expr": "abs(a[0] - b[0]) + abs(a[1] - b[1])"},
        "carres": {"params": ["n"], "expr": "[i * i for i in range(n) if i % 2 == 0]"},
        "norme": {"params": ["v"], "expr": "math.sqrt(sum(x * x for x in v)) if v else 0"},
        "tri": {"params": ["l"], "expr": "sorted(l)[-1] if len(l) > 0 and all(x >= 0 for x in l) else None"}}})
    env = _env(scene())
    assert p.ev(["dist", ["liste", 1, 2], ["liste", 4, 6]], env) == 7
    assert p.ev(["carres", 5], env) == [0, 4, 16]
    assert p.ev(["norme", ["liste", 3, 4]], env) == 5.0
    assert p.ev(["tri", ["liste", 3, 9, 1]], env) == 9
    j = scene().sprites[0]
    with pytest.raises(ErreurLangage, match="simple"):                    # jamais d'objet de la scène
        p.ev(["dist", "$j", "$j"], {**env, "j": j})
    with pytest.raises(ErreurLangage, match="arité"):
        p.ev(["dist", 1], env)


@pytest.mark.parametrize("expr", [
    "__import__('os')", "().__class__", "open('x')", "a.real", "(lambda: 1)()", "math.pi", "a.__class__",
    "eval('1')", "getattr(a, 'x')", "[x for x in ().__class__.__mro__]", "'abc'", "a ** 99", "(x := 1)",
    "globals()", "math", "type(a)", "[_ for _ in range(2)]", "f'{a}'", "import os", "a = 1", "b + 1",
])
def test_fonction_refus_adverses(expr):
    with pytest.raises(ErreurLangage):
        Programme({"fonctions": {"f": {"params": ["a"], "expr": expr}}})


def test_fonction_refus_noms():
    with pytest.raises(ErreurLangage, match="param"):
        Programme({"fonctions": {"f": {"params": ["__a"], "expr": "1"}}})
    with pytest.raises(ErreurLangage, match="natif"):
        Programme({"fonctions": {"liste": {"params": [], "expr": "1"}}})
    with pytest.raises(ErreurLangage, match="déjà"):
        Programme({"mots": {"f": {"params": [], "corps": 1}}, "fonctions": {"f": {"params": [], "expr": "1"}}})


@pytest.mark.parametrize("expr", [
    "[0] * 20000", "list(range(20000))", "len(range(10 ** 6))", "sum(1 for i in range(10000) for j in range(10000))",
    "[i for i in range(9000)] + [i for i in range(9000)]", "[[0] * 9000 for i in range(5000)]",
    "sum([[0] * 9000] * 9000, [])",                      # sum sans « start » : pas de concaténation quadratique
])
def test_fonction_budget(expr):
    try:
        p = Programme({"fonctions": {"f": {"params": [], "expr": expr}}})
    except ErreurLangage:
        return                                           # refus statique : acceptable aussi
    with pytest.raises(ErreurLangage, match="budget|TypeError"):
        p.ev(["f"], _env(scene()))


def test_mots_valides_journal():
    regles = {"mots": {"j": {"params": [], "corps": ["premier", ["objets", {"tag": "joueur"}]]},
                       "p": {"params": ["$o"], "sorte": "effet", "corps": [["deplacer", "$o", 1, 0]]}},
              "fonctions": {"d": {"params": ["a", "b"], "expr": "a - b"}}}
    j = mots_valides(regles)
    assert [(m["nom"], m["genre"], m["signature"]) for m in j] == [
        ("d", "fonction", "d(a, b) -> valeur"), ("j", "mot", "j() -> terme"), ("p", "mot", "p($o) -> effet")]
    assert all(len(m["sha"]) == 12 for m in j)
    regles["fonctions"]["d"]["expr"] = "b - a"
    assert mots_valides(regles)[0]["sha"] != j[0]["sha"] and mots_valides(regles)[1]["sha"] == j[1]["sha"]
    assert mots_valides({"regles": []}) == []
    with pytest.raises(ErreurLangage):
        mots_valides({"fonctions": {"f": {"params": [], "expr": "open('x')"}}})


def test_macro_avec_mots_lieurs_recents():
    """Les mots lieurs ajoutés en v0.2 (trier, tant_que, soit_creer) sont acceptés dans le corps d'une macro."""
    p = Programme({"mots": {"tri_x": {"params": ["$l"], "corps": ["trier", "$l", "$o", ["x", "$o"]]}},
                   "regles": []})
    sc = Scene((4, 4), 0, 1, [{"tags": ["a"], "pixels": [[1]], "x": 2, "y": 0, "couche": 0},
                              {"tags": ["a"], "pixels": [[1]], "x": 0, "y": 0, "couche": 0}])
    env = {"_scene": sc, "_action": ("UP", None, None)}
    assert [o["x"] for o in p.ev(["tri_x", ["objets", {"tag": "a"}]], env)] == [0, 2]


def test_extraire_regles_apres_raisonnement_libre():
    from chrysalide.arc3.langage import extraire_regles
    t = 'Je pense que {le joueur} glisse.\n```json\n{"regles": [{"alors": [["gagner"]]}]}\n```\nFin.'
    assert extraire_regles(t)["regles"][0]["alors"] == [["gagner"]]
    assert extraire_regles('Raisonnement… puis {"etat": {}, "regles": []}')["regles"] == []
    try:
        extraire_regles("rien ici {pas du json}")
        raise AssertionError
    except ErreurLangage:
        pass


# ------------------------------------------------------------- v0.3 : mots demandés par B (CCM-098)
def _sc3(**kw):
    return Scene((4, 8), 0, 1, [
        {"nom": "porte-rouge-3", "tags": ["porte", "b"], "pixels": [[1, 2], [3, 4]], "x": 1, "y": 1, "couche": 0,
         "cache": {"rotation": 90, "mirror_ud": False, "mirror_lr": False}},
        {"nom": "mur", "tags": [], "pixels": [[5]], "x": 4, "y": 1, "couche": 0, "echelle": 2}], **kw)


def test_v0_3_donnees_de_niveau_et_attr_cache():
    sc = _sc3(donnees={"elp": [[0, 1, 0]], "rot": 180})
    o = sc.sprites[0]
    env, p = {**_env(sc), "o": o}, Programme({"regles": []})
    assert p.ev(["donnees_de_niveau", "rot"], env) == 180 and p.ev(["donnees_de_niveau", "zz"], env) is None
    p.ev(["donnees_de_niveau", "elp"], env)[0][0] = 9                     # copie : la donnée du niveau ne bouge pas
    assert sc.donnees["elp"] == [[0, 1, 0]]
    assert p.ev(["attr_cache", "$o", "rotation"], env) == 90
    p.fait(["tourner", "$o", 1], env)                                       # tourner tient la rotation du moteur à jour
    assert p.ev(["attr_cache", "$o", "rotation"], env) == 180


def test_v0_3_forme_modele_et_poser_motif():
    import numpy as np
    sc = _sc3(modeles={"panier": np.array([[7, 8]])})
    porte, mur = sc.sprites
    env, p = {**_env(sc), "o": porte, "m": mur}, Programme({"regles": []})
    assert p.ev(["forme_modele", "panier"], env) == [[7, 8]] and p.ev(["forme_modele", "zz"], env) is None
    p.fait(["poser_motif", "$o", ["forme_modele", "panier"]], env)         # rotation 90 du sprite appliquée
    assert porte["pixels"].tolist() == [[7], [8]] and (porte["x"], porte["y"]) == (1, 1)
    p.fait(["poser_motif", "$m", [[1, 2]]], env)                            # échelle 2 appliquée
    assert mur["pixels"].tolist() == [[1, 1, 2, 2], [1, 1, 2, 2]]
    sprite = pytest.importorskip("arcengine").Sprite                        # même rendu que le moteur
    s = sprite([[1, 2, 3], [4, 5, 6]], rotation=270, mirror_lr=True)
    o = {"pixels": np.asarray(s.render()), "x": 0, "y": 0, "couche": 0,
         "cache": {"rotation": 270, "mirror_ud": False, "mirror_lr": True}}
    sc.poser_motif(o, [[9, 8], [7, 6]])
    s.pixels = np.array([[9, 8], [7, 6]])
    assert np.array_equal(o["pixels"], s.render())


def test_v0_3_chaines_prefixe_segment_tags():
    sc = _sc3()
    env, p = {**_env(sc), "o": sc.sprites[0]}, Programme({"regles": []})
    assert p.ev(["prefixe", ["nom", "$o"], 5], env) == "porte" and p.ev(["prefixe", "abc9", -1], env) == "abc"
    assert p.ev(["segment", ["nom", "$o"], "-", 1], env) == "rouge" and p.ev(["segment", "a-b", "-", -1], env) == "b"
    assert p.ev(["segment", "a-b", "-", 5], env) is None
    assert p.ev(["tags", "$o"], env) == ["porte", "b"] and p.ev(["tags", None], env) == []
    p.ev(["tags", "$o"], env).append("x")                                   # copie
    assert sc.sprites[0]["tags"] == ["porte", "b"]


def test_v0_3_instantane_restaurer():
    p = Programme({"etat": {"k": 1}, "regles": [
        {"quand": ["=", ["action"], "SPACE"], "alors": [["instantane", "avant"]], "puis": "continuer"},
        {"quand": ["=", ["action"], "UNDO"], "alors": [["restaurer", "avant"]]},
        {"soit": {"o": ["premier", ["objets", {"tag": "porte"}]]},
         "alors": [["deplacer", "$o", 1, 0], ["poser_attr", "$o", "vu", 1], ["poser", "k", ["+", ["etat", "k"], 1]],
                   ["retirer", ["premier", ["objets", {"nom": "mur"}]]]]}]})
    sc = _sc3()
    p.step(sc, ("SPACE", None, None))                                       # instantané AVANT les effets du coup
    assert sc.sprites[0]["x"] == 2 and len(sc.sprites) == 1 and p.etat["k"] == 2
    p.step(sc, ("UNDO", None, None))
    assert [o["x"] for o in sc.sprites] == [1, 4] and "attrs" not in sc.sprites[0] and p.etat["k"] == 1
    p.step(sc, ("UNDO", None, None))                                        # l'instantané reste réutilisable
    assert len(sc.sprites) == 2
    p.fait(["restaurer", "inconnu"], _env(sc))                              # nom inconnu : ignoré


def test_v0_3_poser_bloquant_et_rendre_intangible():
    sc = _sc3()
    a, b = sc.sprites
    b["x"], b["y"] = 1, 1
    env, p = {**_env(sc), "a": a, "b": b}, Programme({"regles": []})
    assert p.ev(["contact_moteur", "$a", "$b"], env)
    p.fait(["rendre_intangible", "$b"], env)
    assert not p.ev(["bloquant", "$b"], env) and not p.ev(["contact_moteur", "$a", "$b"], env)
    p.fait(["poser_bloquant", "$b", True], env)
    assert p.ev(["bloquant", "$b"], env) and p.ev(["contact_moteur", "$a", "$b"], env)


def test_v0_3_niveau_suivant_au_dernier_niveau_gagne():
    p = Programme({"regles": [{"alors": [["si_alors", ["dernier_niveau"], [["poser", "d", 1]]], ["niveau_suivant"]]}]})
    sc = _sc3(n_niveaux=3, niveau=1)
    p.step(sc, ("UP", None, None))
    assert sc.issue == "niveau" and "d" not in p.etat
    sc = _sc3(n_niveaux=3, niveau=2)
    p.step(sc, ("UP", None, None))
    assert sc.issue == "victoire" and p.etat["d"] == 1
    sc = _sc3()                                                              # nombre de niveaux inconnu : jamais victoire
    p.step(sc, ("UP", None, None), niveau=99)
    assert sc.issue == "niveau"


def test_v0_3_argmin_argmax_et_portee_macro():
    sc = Scene((4, 8), 0, 1, [{"tags": ["a"], "pixels": [[1]], "x": x, "y": y, "couche": 0}
                              for x, y in ((3, 0), (1, 2), (1, 0), (5, 2))])
    env, p = _env(sc), Programme({"regles": []})
    assert p.ev(["argmin", "$o", ["objets", {}], ["x", "$o"]], env) is sc.sprites[1]   # égalité : le 1er de la liste
    assert p.ev(["argmax", "$o", ["objets", {}], ["y", "$o"]], env) is sc.sprites[1]
    assert p.ev(["argmin", "$o", ["liste"], ["x", "$o"]], env) is None
    q = Programme({"mots": {"plus_a_gauche": {"params": ["$l"], "corps": ["argmin", "$e", "$l", ["x", "$e"]]},
                            "t": {"params": ["$o"], "corps": ["segment", ["prefixe", ["nom", "$o"], 3], "-", 0]},
                            "e": {"params": ["$o"], "sorte": "effet",
                                  "corps": [["poser_motif", "$o", ["forme_modele", "m"]], ["rendre_intangible", "$o"],
                                            ["poser_bloquant", "$o", ["donnees_de_niveau", "k"]], ["instantane", "n"],
                                            ["restaurer", "n"], ["si_alors", ["dernier_niveau"], []],
                                            ["poser_attr", "$o", "t", ["tags", "$o"]],
                                            ["poser_attr", "$o", "r", ["attr_cache", "$o", "rotation"]]]}}})
    assert q.ev(["plus_a_gauche", ["objets", {}]], env) is sc.sprites[1]
    with pytest.raises(ErreurLangage, match="variable"):
        Programme({"mots": {"f": {"params": [], "corps": ["argmin", "$e", ["objets", {}], ["x", "$z"]]}}})


def test_mode_lois_phases():
    """Phase 1 jugée APRÈS les effets de la phase 0 (CCM-020-C) : le joueur avance sur la pièce, puis la consomme."""
    j, pc = ["premier", ["objets", {"tag": "j"}]], ["premier", ["objets", {"tag": "p"}]]
    prog = {"mode": "lois", "regles": [
        {"nom": "consomme", "phase": 1, "quand": ["chevauche", j, pc], "alors": [["retirer", pc]]},
        {"nom": "avance", "quand": ["=", ["action"], "RIGHT"], "alors": [["deplacer", j, 1, 0]]}]}
    for phase, reste in ((1, 1), (0, 2)):
        prog["regles"][0]["phase"] = phase
        sc = Scene((4, 4), 0, 1, [{"tags": ["j"], "pixels": [[1]], "x": 0, "y": 0, "couche": 1},
                                  {"tags": ["p"], "pixels": [[2]], "x": 1, "y": 0, "couche": 0}])
        Programme(prog).step(sc, ("RIGHT", None, None))
        assert sc.sprites[0]["x"] == 1 and len(sc.sprites) == reste


# ------------------------------------------------------------------ v0.4 (CW-128 c) : correspond, jauge, recharge
_MOTIF = [[1, 1, 1], [0, 0, 1], [1, 0, 1]]  # dessin de la porte de ls20 niveau 1 (CCM-027-C)


def _porte(motif=_MOTIF):  # 5×5 : cadre 5, dessin 9 sur fond 5
    return [[5] * 5] + [[5] + [9 if v else 5 for v in ligne] + [5] for ligne in motif] + [[5] * 5]


def _cle(motif=_MOTIF, k=2):  # dessin agrandi ×k, couleur 12 sur transparent
    return [[12 if motif[r // k][c // k] else -1 for c in range(3 * k)] for r in range(3 * k)]


def test_v0_4_correspond_echelle_et_rotation():
    import numpy as np

    from chrysalide.arc3.logique.correspond import correspond as correspond_c
    autre = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    sc = Scene((16, 16), 0, 1, [
        {"tags": ["porte"], "pixels": _porte(), "x": 0, "y": 0, "couche": 0},
        {"tags": ["cle"], "pixels": _cle(), "x": 6, "y": 0, "couche": 0},
        {"tags": ["autre"], "pixels": _cle(autre, 3), "x": 0, "y": 6, "couche": 0}])
    p = Programme({"regles": []})
    env = {"_scene": sc, "_action": ("UP", None, None)}
    porte, cle, autre_o = sc.sprites
    m = lambda op, a, b: p.ev([op, ["premier", ["objets", {"tag": a}]], ["premier", ["objets", {"tag": b}]]], env)
    assert m("correspond", "cle", "porte") and m("correspond_rot", "cle", "porte") == 0
    assert not m("correspond", "autre", "porte") and m("correspond_rot", "autre", "porte") is None
    for q in (1, 2, 3):  # clé tournée de q quarts : il faut encore (4 - q) quarts de tourner pour retrouver la porte
        sc.tourner(cle, 1)
        assert m("correspond", "cle", "porte") and m("correspond_rot", "cle", "porte") == 4 - q
    sc.tourner(cle, 1)
    # égalité avec la fonction de référence de C (sans rotation) sur ses cas, et rotation = un des 4 quarts de C
    for a, b in ((cle, porte), (porte, cle), (autre_o, porte), (cle, cle), (autre_o, autre_o)):
        pa, pb = np.asarray(a["pixels"]), np.asarray(b["pixels"])
        q = p.ev(["correspond_rot", "$a", "$b"], {**env, "a": a, "b": b})
        assert (q == 0) == correspond_c(pa, pb)
        assert (q is not None) == any(correspond_c(np.rot90(pa, -k), pb) for k in range(4))
    assert p.ev(["correspond", None, "$b"], {**env, "b": porte}) is False


def _jeu_jauge():
    j, r = ["premier", ["objets", {"tag": "j"}]], ["objets", {"tag": "r"}]
    return {"au_debut": [["poser", "jauge", 2]], "regles": [
        {"nom": "pas", "quand": ["=", ["action"], "RIGHT"], "puis": "continuer",
         "alors": [["deplacer", j, 1, 0], ["consommer", "jauge", 1]]},
        {"nom": "recharge", "quand": True, "puis": "continuer",
         "alors": [["pour", "$r", r, [["si_alors", ["chevauche", j, "$r"], [["recharger", "jauge", 3, "$r"]]]]]]},
        {"nom": "épuisée", "quand": ["epuise", "jauge"], "alors": [["perdre"]]}]}


def _scene_jauge():
    return Scene((1, 8), 0, 1, [{"tags": ["j"], "pixels": [[1]], "x": 0, "y": 0, "couche": 1},
                                {"tags": ["r"], "pixels": [[2]], "x": 1, "y": 0, "couche": 0}])


def test_v0_4_jauge_recharge_usage_unique_et_defaite():
    p, sc = Programme(_jeu_jauge()), _scene_jauge()
    r = sc.sprites[1]
    p.step(sc, ("RIGHT", None, None))  # sur la recharge : 2 - 1 puis remise à 3, recharge utilisée et masquée
    assert p.etat["jauge"] == 3 and r["attrs"]["utilise"] is True and r["visible"] is False and sc.issue is None
    env = {"_scene": sc, "_action": ("UP", None, None), "r": r}
    assert p.ev(["utilise", "$r"], env) is True and p.ev(["utilise", None], env) is False
    p.fait(["recharger", "jauge", 9, "$r"], env)  # déjà utilisée : ne recharge plus
    assert p.etat["jauge"] == 3
    for attendu in (2, 1):
        p.step(sc, ("RIGHT", None, None))
        assert p.etat["jauge"] == attendu and sc.issue is None
    p.step(sc, ("RIGHT", None, None))
    assert p.etat["jauge"] == 0 and sc.issue == "defaite"
    assert p.ev(["epuise", "jauge", -1], env) is False and p.ev(["epuise", "absente"], env) is True
    p.fait(["consommer", "neuve", 4], env)  # jauge absente = 0
    assert p.etat["neuve"] == -4 and p.ev(["epuise", "neuve", -4], env) is True


def test_v0_4_mots_dans_macros_et_profil_c():
    from chrysalide.arc3.profil_c import hors_profil
    prog = {"mots": {"vide_j": {"params": [], "corps": ["epuise", "jauge"]},
                     "prendre": {"params": ["$o"], "sorte": "effet",
                                 "corps": [["consommer", "jauge", 1], ["recharger", "jauge", 5, "$o"]]},
                     "pareil": {"params": ["$a", "$b"], "corps": ["et", ["correspond", "$a", "$b"],
                                                                  ["=", ["correspond_rot", "$a", "$b"], 0],
                                                                  ["non", ["utilise", "$a"]]]}},
            "regles": [{"soit": {"o": ["premier", ["objets", {"tag": "r"}]]}, "quand": ["non", ["vide_j"]],
                        "alors": [["prendre", "$o"]]}]}
    p, sc = Programme({**prog, "etat": {"jauge": 2}}), _scene_jauge()
    p.step(sc, ("UP", None, None))
    assert p.etat["jauge"] == 5 and sc.sprites[1]["attrs"]["utilise"]
    with pytest.raises(ErreurLangage, match="variable"):
        Programme({"mots": {"f": {"params": [], "sorte": "effet", "corps": [["recharger", "jauge", 1, "$z"]]}}})
    regle = {"soit": {"o": ["premier", ["objets", {"tag": "r"}]]},
             "quand": ["et", ["epuise", "jauge", -1], ["non", ["utilise", "$o"]],
                       ["correspond", "$o", ["premier", ["objets", {"tag": "p"}]]]],
             "alors": [["recharger", "jauge", 3, "$o"], ["consommer", "jauge", 1]]}
    assert hors_profil(regle) == []
    assert len(hors_profil({"quand": ["epuise", "jauge", ["etat", "s"]],
                            "alors": [["consommer", "jauge", ["etat", "k"]]]})) == 2


def test_v0_5_section_niveau_et_param():
    """Étage 2 (CW-132) : ["param", clé] lit la section « niveau » au niveau courant, repli sur "*", sinon None."""
    from chrysalide.arc3.profil_c import hors_profil
    prog = {"niveau": {"1": {"cout": 2, "cibles": [[1, 2]]}, "*": {"cout": 1, "recharges": 3}},
            "mots": {"cout_j": {"params": [], "corps": ["param", "cout"]}},
            "regles": [{"quand": True, "alors": [["consommer", "jauge", ["param", "cout"]]]}]}
    p = Programme({**prog, "etat": {"jauge": 10}})
    sc0, sc1 = _sc3(niveau=0), _sc3(niveau=1)
    assert p.ev(["param", "cout"], _env(sc0)) == 1 and p.ev(["param", "cout"], _env(sc1)) == 2
    assert p.ev(["param", "recharges"], _env(sc1)) == 3                    # clé absente du niveau : repli sur "*"
    assert p.ev(["param", "zz"], _env(sc1)) is None and p.ev(["cout_j"], _env(sc1)) == 2
    assert p.ev(["param", "cout"], {**_env(_sc3()), "_niveau": 1}) == 2    # scène sans niveau : _niveau du coup
    p.ev(["param", "cibles"], _env(sc1))[0][0] = 9                         # copie : la section ne bouge pas
    assert prog["niveau"]["1"]["cibles"] == [[1, 2]]
    assert Programme({"regles": []}).ev(["param", "cout"], _env(sc1)) is None  # sans section
    p.step(sc1, ("UP", None, None))
    assert p.etat["jauge"] == 8
    assert hors_profil(prog["regles"][0]) == []                            # param à clé constante : admis
    assert hors_profil({"quand": True, "alors": [["consommer", "jauge", ["param", ["etat", "k"]]]]})


# ---------------------------------------------------------------- v0.6 canevas (CW-141/142)
def _sc_cv():
    import numpy as np

    from chrysalide.arc3.ontologie_exec import nouveau_canevas
    g = np.array([[1, 1, -1, 2], [1, -1, 2, 2], [-1, -1, -1, 1]])
    return Scene((8, 8), 0, 1, [{"nom": "s", "pixels": [[7]], "x": 0, "y": 0, "couche": 0}],
                 canevas=[nouveau_canevas("plateau", g, x=-2, y=4, kx=4, ky=2)])


def test_v0_6_canevas_rendu_par_dessus_les_sprites():
    import numpy as np
    sc = _sc_cv()
    im, sans = sc.image_complete(), sc.image()
    assert sans[0, 0] == 7 and np.array_equal(sans[8:, :], np.zeros((56, 64)))  # sprite à l'échelle 8, sans canevas
    assert im[4, 0] == 1 and im[4, 1] == 1 and im[4, 2] == 1  # case (0, 0) coupée au bord (x = -2), puis case (1, 0)
    assert im[4, 6] == 7 and im[9, 0] == 0  # case −1 : transparente (sprite, puis fond, dessous)
    assert im[4, 10] == 2 and im[6, 6] == 2 and im[9, 10] == 1 and im[4, 14] == 0  # hors grille : rien de dessiné
    assert (im[:4] == sans[:4]).all() and (im[10:] == sans[10:]).all()


def test_v0_6_termes_canevas():
    sc = _sc_cv()
    p, env = Programme({"regles": []}), {"_scene": sc, "_action": ("CLICK", 6, 7)}
    c = p.ev(["canevas"], env)
    assert c is p.ev(["canevas", "plateau"], env) and p.ev(["canevas", "autre"], env) is None
    assert p.ev(["case_canevas", c, 3, 0], env) == 2 and p.ev(["case_canevas", c, 4, 0], env) is None and p.ev(["case_canevas", None, 0, 0], env) is None
    assert p.ev(["cases_de", c, 2], env) == [[3, 0], [2, 1], [3, 1]] and p.ev(["cases_de", None, 2], env) == []
    assert p.ev(["geometrie", c], env) == [-2, 4, 4, 2]
    assert p.ev(["pixel_clic"], env) == [2, 1] and p.ev(["pixel_clic", c], env) == [2, 1]  # ligne 6, colonne 7
    assert p.ev(["pixel_clic"], {**env, "_action": ("CLICK", 2, 7)}) is None  # hors canevas
    assert p.ev(["pixel_clic"], {**env, "_action": ("UP", None, None)}) is None
    assert [p.ev(["largeur", c], env), p.ev(["hauteur", c], env), p.ev(["x", c], env)] == [4, 3, -2]
    comps = p.ev(["composantes_canevas", c], env)
    assert [(o["couleur"], o["x"], o["y"], len(o["cases"])) for o in comps] == [(1, 0, 0, 3), (2, 2, 0, 3), (1, 3, 2, 1)]
    o = comps[1]
    assert p.ev(["largeur", "$o"], {**env, "o": o}) == 2 and p.ev(["hauteur", "$o"], {**env, "o": o}) == 2
    assert p.ev(["pixel", "$o", 0, 0], {**env, "o": o}) == -1 and o["cases"] == [[3, 0], [2, 1], [3, 1]]
    assert [o["couleur"] for o in p.ev(["composantes_canevas", c, {"couleur": [2]}], env)] == [2]
    sc.canevas[0]["pixels"][0, 1] = -1  # couleur 1 en (0, 0), (1, 1), (3, 2) : (0, 0)-(1, 1) en diagonale seulement
    sc.canevas[0]["pixels"][1, 1] = 1
    sc.canevas[0]["pixels"][1, 0] = -1
    assert len(p.ev(["composantes_canevas", c, {"couleur": 1}], env)) == 3
    assert len(p.ev(["composantes_canevas", c, {"couleur": 1, "connexite": 8}], env)) == 2


def test_v0_6_effets_canevas():
    import numpy as np
    sc = _sc_cv()
    c = sc.canevas[0]
    p = Programme({"regles": [{"soit": {"c": ["canevas"]}, "alors": [
        ["ecrire_case", "$c", 2, 2, 5], ["ecrire_case", "$c", 9, 9, 5],
        ["remplir", "$c", 3, 1, 5, 5, 6],
        ["deplacer_bloc", "$c", 0, 0, 2, 2, 1, 1, 0],
        ["ecrire_case", ["canevas", "absent"], 0, 0, 3]]}]})
    p.step(sc, ("UP", None, None))
    assert np.array_equal(c["pixels"], [[0, 0, -1, 2], [0, 1, 1, 6], [-1, 1, 5, 6]])  # transparents du bloc : n'effacent rien
    p2 = Programme({"regles": [{"alors": [["poser_geometrie", ["canevas"], 0, 0, 2], ["poser_geometrie", ["canevas"], 0, 0, 0]]}]})
    p2.step(sc, ("UP", None, None))
    assert p.ev(["geometrie", ["canevas"]], {"_scene": sc, "_action": ("UP", None, None)}) == [0, 0, 2, 2]  # k = 0 ignoré
    assert sc.image_complete()[0, 0] == 0 and sc.image_complete()[0, 6] == 2


def test_v0_6_instantane_garde_les_canevas():
    sc = _sc_cv()
    p = Programme({"regles": [
        {"quand": ["=", ["action"], "UNDO"], "alors": [["restaurer", "a"]]},
        {"alors": [["instantane", "a"], ["remplir", ["canevas"], 0, 0, 4, 3, 9]]}]})
    p.step(sc, ("UP", None, None))
    assert (sc.canevas[0]["pixels"] == 9).all()
    p.step(sc, ("UNDO", None, None))
    assert sc.canevas[0]["pixels"][0, 3] == 2 and sc.canevas[0]["pixels"][0, 2] == -1


def test_v0_6_geometrie_deduite_et_portee():
    import numpy as np

    from chrysalide.arc3.langage import utilise_canevas
    from chrysalide.arc3.ontologie_exec import dessiner_canevas, geometrie_canevas, nouveau_canevas, regriller
    from chrysalide.arc3.profil_c import hors_profil
    g = np.array([[3, -1, 4], [5, 5, -1]])
    cal = dessiner_canevas(np.full((64, 64), -1, dtype=np.int16), [nouveau_canevas("i", g, x=-1, y=10, kx=3)])
    px, x, y, k = geometrie_canevas(cal)
    assert (k, x, y) == (3, -1, 10) and np.array_equal(px, g)
    assert regriller(cal, nouveau_canevas("i", px, x, y, k)) is not None
    assert regriller(cal, nouveau_canevas("i", px, x + 1, y, k)) is None  # géométrie qui ne redonne pas le calque
    bruit = cal.copy()
    bruit[10, 0] = 7
    assert geometrie_canevas(bruit)[3] == 1  # plus de grille unie : case = pixel
    assert utilise_canevas({"regles": [{"alors": [["pour", "$x", [], [["remplir", ["canevas"], 0, 0, 1, 1, 0]]]]}]})
    assert not utilise_canevas({"regles": [{"alors": [["deplacer", "$o", 1, 0]]}], "note": "canevas"})
    assert hors_profil({"quand": ["=", ["case_canevas", ["canevas"], 1, 2], 3], "alors": [["ecrire_case", ["canevas", "i"], 0, 0, 1]]}) == []
    assert hors_profil({"alors": [["remplir", ["canevas"], ["etat", "x"], 0, 1, 1, 1]]})
    Programme({"mots": {"m": {"params": ["$c"], "sorte": "effet", "corps": [["deplacer_bloc", "$c", 0, 0, 1, 1, 1, 0]]},
                        "t": {"params": [], "corps": ["composantes_canevas", ["canevas"], {"couleur": 1}]}}})


def test_objets_dans_boite_transparent_inclus_debordant_exclu():
    """Mot `objets_dans_boite` (CCM-159-B) : un sprite tout transparent posé dans la case est rendu ; un sprite qui déborde, non ;
    l'ordre suit les calques (haut d'abord), et les invisibles comptent ; interpréteur et simulateur compilé d'accord."""
    from chrysalide.arc3.sim_rapide import ProgrammeCompile
    sc = Scene((4, 8), 0, 1, [
        {"tags": ["vide"], "pixels": [[-1, -1], [-1, -1]], "x": 2, "y": 0, "couche": 0},
        {"tags": ["haut"], "pixels": [[4]], "x": 3, "y": 1, "couche": 2},
        {"tags": ["deborde"], "pixels": [[5, 5, 5]], "x": 2, "y": 1, "couche": 1},
    ])
    vide, haut, _deborde = sc.sprites
    sc.montrer(haut, False)
    terme = ["objets_dans_boite", 2, 0, 2, 2]
    p = Programme({"regles": []})
    assert p.ev(terme, {"_scene": sc, "_action": ("UP",)}) == [haut, vide]
    pc = ProgrammeCompile({"regles": [{"nom": "t", "quand": ["=", ["longueur", terme], 2], "alors": [["gagner"]]}]})
    pc.step(sc, ("UP", None, None))
    assert sc.issue == "victoire"
