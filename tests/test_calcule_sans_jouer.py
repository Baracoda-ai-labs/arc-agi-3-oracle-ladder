"""D (charte, CHRYS_CALCULE_SANS_JOUER) : un plan prêt du moteur est noté puis jeté, aucun coup n'est joué, Franzen joue ;
drapeau éteint : le 1er coup du plan est joué."""
from chrysalide.arc3 import branche
from tests.test_evenements import _Solveur


def _b(monkeypatch, tmp_path, flag):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_MONITEUR", "1")
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    monkeypatch.setenv("CHRYS_CALCULE_SANS_JOUER", flag)
    from chrysalide.arc3.moteur import MoteurC
    s = _Solveur()
    b = branche.creer(s, tmp_path, moteur=MoteurC(budget=1))
    b.plan = {"actions": [{"action": "UP"}, {"action": "UP"}], "pas": 0}
    return s, b


def test_plan_jete_sans_coup(monkeypatch, tmp_path):
    s, b = _b(monkeypatch, tmp_path, "1")
    assert b._jouer_plan() is False and s.n == 0 and b.plan is None and b.m["plans_non_joues"] == 1


def test_eteint_le_plan_est_joue(monkeypatch, tmp_path):
    s, b = _b(monkeypatch, tmp_path, "0")
    assert b._jouer_plan() is True and s.n == 1
