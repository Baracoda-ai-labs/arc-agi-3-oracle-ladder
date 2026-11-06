"""Outils V2' du REPL : exécutés dans un espace de noms qui imite le bac à sable de Franzen (history, current_frame, action)."""
import ast
from types import SimpleNamespace as NS

from chrysalide.arc3 import outils_repl
from chrysalide.arc3.masque import Masque


def ascii_(pos, pas):
    g = [["0"] * 16 for _ in range(16)]
    g[8][2 + pos] = "3"
    for c in range(min(pas, 16)):  # barre de pas en haut : change à chaque coup, ne revient jamais
        g[0][c] = "5"
    return ["".join(r) for r in g]


class Jeu:
    """Couloir : RIGHT avance, LEFT recule ; RIGHT depuis la case 3 tue (game over puis RESET au départ)."""
    def __init__(self):
        self.pos, self.pas = 0, 0
        self.ns = {"history": [NS(action="", frame=NS(ascii=ascii_(0, 0), level=0), result={})]}
        self.ns["current_frame"] = self.ns["history"][-1].frame
        self.ns["action"] = self.jouer

    def jouer(self, a):
        a = a if isinstance(a, str) else a["action"]
        mort = a == "RIGHT" and self.pos == 3
        self.pos = 0 if mort else (self.pos + 1 if a == "RIGHT" else max(0, self.pos - 1))
        self.pas += 1
        f = NS(ascii=ascii_(self.pos, self.pas), level=0)
        self.ns["history"].append(NS(action=a, frame=f, result={"game_over": mort}))
        if mort:
            self.pas = 0
            f = NS(ascii=ascii_(0, 0), level=0)
            self.ns["history"].append(NS(action="RESET", frame=f, result={}))
        self.ns["current_frame"] = f


def charger(jeu):
    for src in outils_repl.SOURCES:
        exec(compile(src, "<retained>", "exec"), jeu.ns, jeu.ns)  # noqa: S102 — imite la restauration du bac à sable
    return jeu.ns


def test_sources_respectent_les_regles_de_retention_de_franzen():
    for src in outils_repl.SOURCES:
        t = ast.parse(src)
        assert len(t.body) == 1 and isinstance(t.body[0], ast.FunctionDef)
        f = t.body[0]
        assert not f.decorator_list and f.returns is None and all(a.annotation is None for a in f.args.args)
        for d in f.args.defaults:
            ast.literal_eval(d)
        assert not any(isinstance(n, ast.Global) for n in ast.walk(t))


def test_retour_mortel_et_aller():
    j = Jeu()
    ns = charger(j)
    for a in ["RIGHT"] * 4:  # mort au 4e
        j.jouer(a)
    assert ns["chrys_mortel"]("RIGHT") is False  # au départ : RIGHT n'est pas mortel ici
    for _ in range(9):
        j.jouer("LEFT")  # la barre avance : sans masque, chaque état serait nouveau
    carte = ns["chrys_carte"]()
    assert carte["cases_masquees"] >= 16 and carte["coups_mortels"] == 1
    assert ns["chrys_chemin"](3) == ["RIGHT", "RIGHT", "RIGHT"]  # history[3] = case 3 (juste avant le coup fatal)
    r = ns["chrys_aller"](3)
    assert r == {"joues": 3, "arrive": True} and j.pos == 3
    assert ns["chrys_mortel"]("RIGHT") is True and ns["chrys_mortel"]("LEFT") is False


def test_masque_identique_a_celui_de_b():
    j = Jeu()
    for a in ["RIGHT", "RIGHT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "LEFT", "LEFT", "RIGHT", "RIGHT"]:
        j.jouer(a)
    ns = charger(j)
    m, prec = Masque(), None
    for h in j.ns["history"]:
        g = [list(r) for r in h.frame.ascii]
        if prec is not None and h.action != "RESET" and not h.result.get("game_over"):
            m.observer(prec, g)
        if h.action == "RESET" or h.result.get("game_over"):
            m.nouvelle_vie()
        prec = g
    assert ns["chrys_carte"]()["cases_masquees"] == len(m.cellules()) > 0


def test_chrys_verifier_juge_la_regle_du_modele(monkeypatch):
    j = Jeu()
    for a in ["RIGHT", "RIGHT", "LEFT", "RIGHT"]:
        j.jouer(a)
    exec(compile(outils_repl.VERIFIER, "<retained>", "exec"), j.ns, j.ns)  # noqa: S102 — imite la restauration
    juste = ("def predire(g, a):\n    import copy\n    g = copy.deepcopy(g)\n    r = 8\n    c = g[r].index('3')\n"
             "    g[r][c] = '0'\n    g[r][c + (1 if a == 'RIGHT' else -1 if c > 2 else 0)] = '3'\n    return g\n")
    fausse = "def predire(g, a):\n    return g\n"
    for src in (juste, fausse):
        exec(compile(src, "<llm>", "exec"), j.ns, j.ns)  # noqa: S102
        r = j.ns["chrys_verifier"](j.ns["predire"], bord=1)
        if src is juste:
            assert r["transitions"] == 4 and r["exactitude"] == 1.0 and r["premiere_contradiction"] is None
        else:
            assert r["exactitude"] == 0.0 and r["premiere_contradiction"]["pas"] == 1
            assert r["premiere_contradiction"]["cases_fausses"][0][:2] == (8, 2)


def test_verifier_absent_sans_interrupteur():
    assert outils_repl.VERIFIER not in outils_repl.SOURCES  # V2p (CHRYS_OUTILS seul) garde ses 4 outils
