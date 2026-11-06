"""T2.6 : vérification massive de règles sur un jeu fabriqué (un carré de couleur 3 qui avance d'une case par RIGHT)."""
import json

import numpy as np

from chrysalide.arc3 import verif_massive as vm


def jeu(n=12):
    """Transitions fabriquées : RIGHT déplace la couleur 3 d'une case ; UP ne fait rien."""
    out, x = [], 2
    for i in range(n):
        g0 = np.zeros((16, 16), dtype=np.int8)
        g0[5:7, x:x + 2] = 3
        a = ("RIGHT", None, None) if i % 3 else ("UP", None, None)
        g1 = g0.copy()
        if a[0] == "RIGHT":
            g1[:] = 0
            g1[5:7, x + 1:x + 3] = 3
            x += 1
        out.append((g0, a, g1))
    return out


def test_la_bonne_regle_survit_et_les_autres_sont_contredites():
    t = jeu()
    garde = np.ones((16, 16), dtype=bool)
    r = vm.verifier([("deplace", 3, "RIGHT", 0, 1, 1), ("deplace", 3, "RIGHT", 0, 1, 2), ("identite",)], t, garde, processus=1)
    assert r[0]["exactitude"] == 1.0 and r[0]["premiere_erreur"] is None
    assert r[1]["premiere_erreur"] == 1 and r[1]["exactitude"] < 1
    assert r[2]["classe"] == "mouvement manqué"


def test_source_python_du_llm_et_delai():
    t = jeu(4)
    garde = np.ones((16, 16), dtype=bool)
    bonne = "def predire(g, a):\n    if a[0] != 'RIGHT':\n        return g\n    return np.roll(g, 1, axis=1)\n"
    boucle = "def predire(g, a):\n    while True:\n        pass\n"
    cassee = "def predire(g, a) return g"
    r = vm.verifier([bonne, boucle, cassee], t, garde, processus=1)
    assert r[0]["exactitude"] == 1.0
    assert r[1]["classe"] in ("delai", "mouvement manqué") and r[1]["exactitude"] < 1
    assert r[2]["classe"].startswith("source invalide")


def test_parallele_identique_au_sequentiel():
    t = jeu()
    garde = np.ones((16, 16), dtype=bool)
    specs = vm.generer([3], ["RIGHT", "UP"])
    assert len(specs) > 50
    a, b = vm.verifier(specs, t, garde, processus=1), vm.verifier(specs, t, garde, processus=3)
    assert [x["exactitude"] for x in a] == [x["exactitude"] for x in b]
    assert sum(x["exactitude"] == 1.0 for x in a) >= 1


def test_transitions_depuis_events(tmp_path):
    g = [[0] * 4 for _ in range(4)]
    g2 = [r[:] for r in g]
    g2[1][1] = 3
    lignes = [{"type": "initial", "board": json.dumps(g), "level": "1"},
              {"type": "action", "board": json.dumps(g2), "level": "1", "action_name": "ACTION6",
               "action_display": "MOUSE(row=1, col=1)", "game_over": "False", "level_completed": "False"},
              {"type": "action", "board": json.dumps(g), "level": "1", "action_name": "ACTION1", "action_display": "UP",
               "game_over": "True", "level_completed": "False"}]
    f = tmp_path / "x_events.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in lignes))
    t = vm.transitions(f)
    assert len(t) == 1 and t[0][1] == ("MOUSE", 1, 1)  # la transition mortelle est exclue


def test_porte_exacte_et_defauts_plantes():
    t = jeu(9)
    bonne = ("def predire(grille, action):\n    if action[0] != 'RIGHT':\n        return grille\n"
             "    return np.roll(grille, 1, axis=1)\n")
    assert vm.porte(bonne, t)["accepte"] and len(vm.empreinte_verificateur()) == 64
    assert not vm.porte(("deplace", 3, "RIGHT", 0, 1, 2), t)["accepte"]
    r = vm.tester_le_testeur(bonne, t, n=30)
    assert r["valide"] and r["plantes"] >= 10 and r["detectes"] == r["plantes"]


def test_anti_degenerescence():
    table = "def predire(grille, action):\n    T = [" + ",".join(["0"] * 100) + "]\n    return grille\n"
    lit_trace = "def predire(grille, action):\n    return history[-1]\n"
    compteur = "def predire(grille, action):\n    if pas == 3:\n        return grille\n    return grille\n"
    for src, motif in ((table, "table"), (lit_trace, "history"), (compteur, "pas")):
        m = vm.anti_degenere(src)
        assert m and any(motif in x for x in m), (motif, m)
        assert not vm.porte(src, jeu(3))["accepte"]
    assert vm.anti_degenere("def predire(grille, action):\n    return grille\n") == []
