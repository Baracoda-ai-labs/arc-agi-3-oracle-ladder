# SPDX-License-Identifier: MIT-0
"""F (CW-333) : budget dans l'état du planificateur (`CHRYS_ECONOMIE`) — réserve, coup gagnant gratuit, victoire avant
défaite, barème, et drapeau éteint = inchangé."""
from chrysalide.arc3.logique.economie_plan import avec_reserve, categorie_cout, fonction_cout, limite
from chrysalide.arc3.logique.plan import planifier


class Couloir:
    """Un pion sur une ligne : ("pion", x) ; « D » avance de 1, « C » (clic) ne fait rien. But : x = 5.
    `mort_au_but` : la case du but est aussi mortelle (teste l'ordre victoire / défaite)."""
    but = ("x", 5)
    motif = True

    def __init__(self, mort_au_but=False):
        self.mort_au_but = mort_au_but

    def pas(self, m, a, taille, fixe=None):
        (_, x), = m
        return ((("pion", x + 1),) if a == "D" else m), None

    def atteint(self, m):
        return m[0][1] == 5

    def meurt(self, m):
        return self.mort_au_but and m[0][1] == 5


DEPART = (("pion", 0),)


def test_eteint_inchange(monkeypatch):
    monkeypatch.setenv("CHRYS_ECONOMIE", "0")
    with avec_reserve(1):
        assert limite() is None
        plan, _ = planifier(Couloir(), DEPART, 10, ["D"])
    assert plan == ["D"] * 5


def test_reserve_juste_et_coup_gagnant_gratuit(monkeypatch):
    monkeypatch.setenv("CHRYS_ECONOMIE", "1")
    with avec_reserve(5):  # 4 positions non gagnantes (coût ≤ 4), puis le 5ᵉ coup gagne
        plan, _ = planifier(Couloir(), DEPART, 10, ["D"])
    assert plan == ["D"] * 5
    with avec_reserve(4):  # il faudrait une position non gagnante de coût 4 : réserve à 0, perdue
        plan, _ = planifier(Couloir(), DEPART, 10, ["D"])
    assert plan is None
    assert limite() is None  # la réserve ne survit pas à la proposition


def test_victoire_avant_defaite(monkeypatch):
    monkeypatch.setenv("CHRYS_ECONOMIE", "0")
    assert planifier(Couloir(mort_au_but=True), DEPART, 10, ["D"])[0] is None  # comportement historique
    monkeypatch.setenv("CHRYS_ECONOMIE", "1")
    with avec_reserve(10):
        assert planifier(Couloir(mort_au_but=True), DEPART, 10, ["D"])[0] == ["D"] * 5


def test_bareme():
    assert fonction_cout("mouvements")(("CLICK", 3, 4)) == 0 and fonction_cout("mouvements")(("UP", None, None)) == 1
    assert fonction_cout("clics")(("CLICK", 3, 4)) == 1 and fonction_cout("clics")("UP") == 0
    assert fonction_cout("toute_action")("UP") == 1 and fonction_cout("aucun") is None
    assert categorie_cout(None) == "toute_action"


def test_aucun_budget_pas_de_limite(monkeypatch):
    monkeypatch.setenv("CHRYS_ECONOMIE", "1")
    with avec_reserve(1, "aucun"):
        assert limite() is None


def test_bareme_lots_de_l_agent():
    assert fonction_cout("mouvements")({"action": "MOUSE", "row": 3, "col": 4}) == 0
    assert fonction_cout("mouvements")({"action": "UP"}) == 1
    assert fonction_cout("clics")({"action": "MOUSE"}) == 1


def test_reserve_au_debut_du_niveau_par_le_niveau_precedent():
    import numpy as np

    from chrysalide.arc3.logique.economie_plan import reserve_niveau

    def image(t, cases):
        g = np.zeros((64, 64), int)
        g[63, :cases - t // 2] = 15  # barre : une case de moins tous les 2 coups
        g[20, 10 + t % 5] = 3
        return g
    prec = {"grilles": [image(t, 40) for t in range(21)], "lots": [{"action": "UP"}] * 20}
    h = {"grilles": [image(0, 40), image(1, 40)], "lots": [{"action": "UP"}], "precedents": [prec]}
    r = reserve_niveau(h)
    assert r is not None and r["statut"] == "rythme du niveau précédent" and r["coups"] == 72  # prudent : 40 cases × 20 coups / (10 + 1) cases
    assert reserve_niveau({"grilles": h["grilles"], "lots": h["lots"]}) is None  # sans niveau précédent : inconnu


def test_resserrer_prend_le_minimum(monkeypatch):
    from chrysalide.arc3.logique.economie_plan import resserrer
    monkeypatch.setenv("CHRYS_ECONOMIE", "1")
    assert resserrer(10) is None  # aucune réserve posée : sans effet
    with avec_reserve(50):
        assert resserrer(80) == 50 and resserrer(30) == 30 and limite() == 30
    monkeypatch.setenv("CHRYS_ECONOMIE", "0")
    with avec_reserve(50):
        assert resserrer(30) is None


def test_bareme_observe_clics_gratuits():
    import numpy as np

    from chrysalide.arc3.logique.economie_plan import bareme_observe, categorie
    grilles, lots, cases, depense = [], [], 40, 0

    def image(c):
        g = np.zeros((64, 64), int)
        g[63, :c] = 15
        g[20, 10 + len(grilles) % 5] = 3
        return g
    grilles.append(image(cases))
    for t in range(40):
        clic = t % 2 == 1
        if not clic:
            depense += 1
            if depense % 2 == 0:
                cases -= 1  # une case tous les 2 MOUVEMENTS ; les clics ne coûtent rien
        lots.append({"action": "MOUSE"} if clic else {"action": "UP"})
        grilles.append(image(cases))
    lu, det = bareme_observe({"grilles": grilles, "lots": lots})
    assert lu == "mouvements", det
    assert categorie({"grilles": grilles, "lots": lots}) == "mouvements"  # pas de fiche : barème lu
    assert categorie({"grilles": grilles, "lots": lots, "jeu": "ft09-abc"}) == "clics"  # la fiche prime


def _hist_barre(n, clics_gratuits=True, jeu="zz99-x"):
    import numpy as np
    grilles, lots, cases, dep = [], [], 40, 0

    def image(c, t):
        g = np.zeros((64, 64), int)
        g[63, :c] = 15
        g[20, 10 + t % 5] = 3
        return g
    grilles.append(image(cases, 0))
    for t in range(n):
        clic = t % 2 == 1
        if not (clic and clics_gratuits):
            dep += 1
            if dep % 2 == 0:
                cases -= 1
        lots.append({"action": "MOUSE"} if clic else {"action": "UP"})
        grilles.append(image(cases, t + 1))
    return {"grilles": grilles, "lots": lots, "jeu": jeu}


def test_question_economie_verifiee_par_la_barre():
    from chrysalide.arc3.logique import economie_plan as E
    E._QWEN.clear()
    appels = []

    def faux_qwen(type_, dossier, **kw):
        appels.append((type_, sorted(dossier["menu"])))
        return {"statut": "propose", "choix": {"cle": "clics"}, "signature": "sig"}
    court = _hist_barre(3)  # trop peu de coups : barème inconnu → on demande
    assert E.question_economie(court, demander=faux_qwen)["choix"]["cle"] == "clics"
    assert appels and appels[0][0] == "economie"
    assert E.categorie(court) == "toute_action"  # « clics » non vérifié rendrait UP gratuit : pas utilisé
    long = _hist_barre(40)  # la barre tranche : mouvements → la réponse « clics » est réfutée
    assert E.question_economie(long, demander=faux_qwen) is None  # plus de question : le barème est lu
    assert E.verifier_economie(long) == "refute" and E.categorie_qwen("zz99-x") is None


def test_question_inutile_si_fiche():
    from chrysalide.arc3.logique import economie_plan as E
    assert E.question_economie(_hist_barre(3, jeu="ft09-abc"), demander=lambda *a, **k: 1 / 0) is None


def _plan_asp(reserve0, extra=""):
    """Couloir jouet : `avance` fait +1, `attend` ne bouge pas ; gagné en x = 5. → plan minimal ou None."""
    from pathlib import Path

    import clingo
    lp = Path(__file__).resolve().parents[1] / "chrysalide/arc3/logique/economie.lp"
    jeu = f"""
    #const h = 8.
    time(0..h). action(avance; attend).
    reserve0({reserve0}).
    x(0, 0).
    x(X + 1, T + 1) :- x(X, T), does(avance, T), time(T + 1).
    x(X, T + 1) :- x(X, T), does(attend, T), time(T + 1).
    gagne(T) :- x(5, T).
    fini(T) :- gagne(T0), time(T), T >= T0.
    {{ does(A, T) : action(A) }} = 1 :- time(T), time(T + 1), not fini(T).
    :- not gagne(_).
    #minimize {{ 1, T : does(_, T) }}.
    {extra}
    """
    ctl = clingo.Control(["--opt-mode=opt"])
    ctl.load(str(lp))
    ctl.add("base", [], jeu)
    ctl.ground([("base", [])])
    plan = []
    with ctl.solve(yield_=True) as h:
        for m in h:
            plan = sorted((s.arguments[1].number, s.arguments[0].name) for s in m.symbols(atoms=True) if s.name == "does")
        res = h.get()
    return [a for _, a in plan] if res.satisfiable else None


def test_economie_asp_reserve_et_victoire_prioritaire():
    assert _plan_asp(5) == ["avance"] * 5  # la réserve tombe à 0 au coup gagnant : la victoire prime
    assert _plan_asp(4) is None  # 4 coups ne suffisent pas : perdu avant de gagner
    assert _plan_asp(3, "cout(avance, 0).") == ["avance"] * 5  # action gratuite : la réserve ne bouge pas
    assert _plan_asp(4, "recharge(2, 0).") == ["avance"] * 5  # recharge explicite après le 1er coup
    assert _plan_asp(5, "epuisement_d_abord.") is None  # option du jeu : l'épuisement est testé avant la victoire
    assert _plan_asp(6, "epuisement_d_abord.") == ["avance"] * 5


def test_bilan_plan_pour_inspect():
    from chrysalide.arc3.logique.economie_plan import bilan_plan
    plan = [{"action": "UP"}, {"action": "MOUSE"}, {"action": "LEFT"}, {"action": "RIGHT"}]
    assert bilan_plan(plan, None) is None
    assert bilan_plan(plan, {"coups": 3, "cout": "aucun"}) is None
    b = bilan_plan(plan, {"coups": 3, "cout": "toute_action", "statut": "lu"})
    assert b["cost"] == 3 and b["budget_left_after"] == 0 and b["fits"] is False  # le dernier coup est gratuit
    b = bilan_plan(plan, {"coups": 3, "cout": "mouvements"})
    assert b["cost"] == 2 and b["fits"] is True  # le clic est gratuit
