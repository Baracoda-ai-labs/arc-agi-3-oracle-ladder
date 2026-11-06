# SPDX-License-Identifier: MIT-0
"""Porte de confiance (CW-401) : ouverte seulement si la théorie prédit sans erreur les K dernières transitions ; borne
de plan : strictement plus court que 0,8 × les coups de Franzen, et dans la réserve."""
from chrysalide.arc3.logique.confiance import borne_plan, porte
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.theorie import Theorie


def _traj(n=6):
    grilles = []
    for t in range(n + 1):
        g = [[0] * 10 for _ in range(3)]
        g[1][1 + t] = 5
        grilles.append(g)
    return Trajectoire(grilles, [4] * n, ech=(1, 0, 0))


def test_porte():
    tr = _traj()
    juste = Theorie(moves={(5, 4): (1, 0)})
    fausse = Theorie(moves={(5, 4): (2, 0)})
    assert porte(juste, tr, k=5)["ouverte"]
    r = porte(fausse, tr, k=5)
    assert not r["ouverte"] and r["premiere_fausse"] is not None
    assert not porte(juste, tr, k=10)["ouverte"]  # pas assez de transitions vues


def test_borne_plan():
    assert borne_plan(["UP"] * 7, 10) and not borne_plan(["UP"] * 8, 10) and not borne_plan([], 10)
    assert not borne_plan(["UP"] * 5, 10, reserve=4)


def _hist_releve(n=12):
    grilles = []
    for t in range(n + 1):
        g = [[3 if min(x, y) < 4 or max(x, y) >= 60 else 0 for x in range(64)] for y in range(64)]  # 64 × 64, cadre
        for i in range(8, 15):  # blocs fixes de 4 px, irréguliers, sous le couloir : l'échelle 4 se lit
            for j in range(1, 15):
                if (i * 7 + j * 3) % 5 == 0:
                    for k in range(4):
                        g[4 * i + k][4 * j:4 * j + 4] = [2] * 4
        for y in range(8, 12):
            for x in range(4 + 4 * t, 8 + 4 * t):
                g[y][x] = 5
        grilles.append(g)
    prec = {"grilles": grilles, "lots": [{"actions": [{"action": "RIGHT"}]}] * n,
            "finale": {"actions": [{"action": "RIGHT"}]}}
    return {"grilles": [grilles[0]], "lots": [], "precedents": [prec]}


def test_releve_moteur(monkeypatch):
    """CCM-077-D : sous CHRYS_RELEVE, `proposer` refuse si la porte est fermée ou si le plan n'est pas assez court."""
    from chrysalide.arc3 import moteur

    def faux(plan, th):
        def _p(self, h, t0, b):
            self.th_releve = th
            return (plan,)
        return _p
    monkeypatch.setenv("CHRYS_ECONOMIE", "0")
    monkeypatch.setenv("CHRYS_RELEVE", "1")
    juste, fausse = Theorie(moves={(5, 4): (1, 0)}), Theorie(moves={(5, 4): (2, 0)})
    cas = [(juste, [4] * 5, True), (juste, [4] * 11, False), (fausse, [4] * 5, False)]  # 13 coups de Franzen
    for th, plan, passe in cas:
        monkeypatch.setattr(moteur.MoteurC, "_proposer", faux(plan, th))
        m = moteur.MoteurC(budget=60)
        r = m.proposer(_hist_releve())
        assert (r is not None) == passe, m.infos
        assert passe or m.infos["refus"].startswith("relève")
    vide = _hist_releve()
    vide["precedents"][0]["grilles"] = [[[0] * 64 for _ in range(64)]] * 13  # rien de perçu : la porte ne s'ouvre pas
    monkeypatch.setattr(moteur.MoteurC, "_proposer", faux([4] * 5, juste))
    m = moteur.MoteurC(budget=60)
    assert m.proposer(vide) is None and m.infos["refus"].startswith("relève")
    monkeypatch.setenv("CHRYS_RELEVE", "0")  # éteint : plan rendu tel quel
    m = moteur.MoteurC(budget=60)
    assert m.proposer(_hist_releve()) is not None


def test_releve_debut_de_niveau_vrai_jeu(monkeypatch):
    """CW-424 : sous CHRYS_RELEVE, `proposer` doit planifier au DÉBUT du niveau qui suit une victoire (aucun coup du niveau
    vu, `lots` vide), avec la théorie des niveaux gagnés (réinduire sur 0 transition perdait les murs). sk01 N2 : porte
    ouverte (10/10 sur la vie gagnante du N1) ; plan de 19 coups refusé par la borne (≥ 0,8 × 14) ; sans la borne, il gagne."""
    import json
    from pathlib import Path

    import pytest
    pytest.importorskip("clingo")
    pytest.importorskip("arc_agi")
    from chrysalide.arc3 import moteur
    from chrysalide.arc3.logique import confiance
    from chrysalide.arc3.logique.jeux import environnement, jouer_action, segments
    synth = Path("experiments/T2.8/synth_envs")
    if not (synth / "solutions.json").exists():
        pytest.skip("jeux synthétiques absents")
    noms = moteur.NOMS
    gid, sols = "sk01-38abff94", json.loads((synth / "solutions.json").read_text())
    s0, s1 = segments(gid, synth, sols[gid][0] + sols[gid][1][:1])[:2]

    def lots(acts):
        return [{"actions": [{"action": noms[a]}]} for a in acts]
    h = {"grilles": s1["grilles"][:1], "lots": [],
         "precedents": [{"grilles": s0["grilles"], "lots": lots(s0["actions"]), "finale": lots([s0["finale"]])[0]}]}
    monkeypatch.setenv("CHRYS_RELEVE", "0")
    m = moteur.MoteurC(budget=60)
    assert m.proposer(h) is None and m.infos["refus"] == "aucune transition"  # éteint : inchangé
    monkeypatch.setenv("CHRYS_RELEVE", "1")
    m = moteur.MoteurC(budget=60)
    assert m.proposer(h) is None and m.infos["releve"]["ouverte"] and m.infos["refus"].startswith("relève : plan de 19")
    monkeypatch.setattr(confiance, "borne_plan", lambda *a, **k: True)
    m = moteur.MoteurC(budget=60)
    r = m.proposer(h)
    assert r is not None and m.infos.get("releve_ancienne"), m.infos
    env = environnement(gid, synth)
    f = env.reset()
    inv = {v: k for k, v in noms.items()}
    for a in sols[gid][0] + [inv[x["action"]] for x in r[0]]:
        f = jouer_action(env, a)
    assert f.levels_completed == 2


def test_borne_reglable(monkeypatch):
    """CCM-308-C : CHRYS_RELEVE_BORNE règle le facteur (0,8 par défaut) ; 0 = réserve seule."""
    from chrysalide.arc3.logique.confiance import borne_plan
    plan = list(range(19))
    monkeypatch.delenv("CHRYS_RELEVE_BORNE", raising=False)
    assert not borne_plan(plan, 14)                          # 19 ≥ 0,8 × 14 : refusé (défaut inchangé)
    monkeypatch.setenv("CHRYS_RELEVE_BORNE", "2")
    assert borne_plan(plan, 14)
    monkeypatch.setenv("CHRYS_RELEVE_BORNE", "0")
    assert borne_plan(plan, 14) and not borne_plan(plan, 14, reserve=10)
