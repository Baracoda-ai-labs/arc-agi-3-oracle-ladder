"""S1 (b) : « notre Duck » (MIT-0), avec un faux modèle scripté sur un vrai jeu ARC-AGI-3 hors ligne (aucun LLM)."""
from pathlib import Path

import pytest

arc_agi = pytest.importorskip("arc_agi")
import itertools

from chrysalide.arc3.duck import executer, jouer, segmentation

JEUX = Path("experiments/arc3/environment_files")
pytestmark = pytest.mark.skipif(not JEUX.exists(), reason="jeux publics absents")


def env(jeu="ls20-9607627b"):
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(JEUX)).make(jeu)


def test_segmentation():
    g = [[0] * 5 for _ in range(5)]
    g[1][1] = g[1][2] = 3
    g[4][4] = 7
    obj = segmentation(g)
    assert [(o["color"], o["size"]) for o in obj] == [(3, 2), (7, 1)] and obj[0]["bbox"] == (1, 1, 1, 2)


def test_bac_a_sable():
    from chrysalide.arc3.duck import Partie
    e = env(); p = Partie(e, e.reset(), 10)
    assert "[error] ImportError" in executer("import os", p)
    assert "[timeout" in executer("while True:\n    pass", p, delai=1)
    out = executer("r = action('UP')\nprint(r['action'], len(history))\nresult = current_frame.ascii[:4]", p)
    assert out.startswith("UP 0") and "result =" in out and p.n_actions == 1


def test_partie_scriptee():
    rep = iter(["Let me move.\n```python\nfor _ in range(3):\n    action('UP')\nprint(len(history))\n```", "No code this time."] * 20)
    vus = []

    def gen(msgs):
        vus.append(msgs)
        return next(rep)
    r = jouer(env(), gen, max_actions=12, max_tours=10, garder=2)
    assert r["actions"] == 12 and r["appels_outil"] == 4 and r["tours"] == 7  # code, rien, code, rien… : 7 tours pour 4 appels
    roles = [m["role"] for m in vus[-1]]
    assert roles[0] == "user" and all(a != b for a, b in itertools.pairwise(roles)) and len(vus[-1]) <= 1 + 2 * 2 + 1
    assert "Tool output" in vus[1][-1]["content"]


def test_vue_et_fonctions_de_base():
    """Défauts vus à l'essai 27B : ascii parcouru caractère par caractère ; type() absent du bac à sable."""
    from chrysalide.arc3.duck import Partie
    e = env(); p = Partie(e, e.reset(), 5)
    out = executer("print(type(current_frame.ascii).__name__, len(current_frame.ascii), len(current_frame.ascii[0]))", p)
    assert out == "list 64 64"
