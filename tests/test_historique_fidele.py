"""D (charte, CHRYS_HISTORIQUE_FIDELE) : après des coups joués sans Franzen (moteur), le résumé de séquence qu'il lira
décrit CES coups, marqués « (auto) », et non sa propre séquence précédente ; drapeau éteint = résumé inchangé ;
un coup de Franzen remet le compte à zéro."""
from chrysalide.arc3 import branche
from tests.test_evenements import _Solveur


class _Analyseur:
    def __init__(self):
        self._last_step_summary = {"executed_actions": ["LEFT"], "executed_count": 1}  # sa propre séquence

    @staticmethod
    def _summarize_step_sequence(res):
        ex = [r for r in res if r.get("executed")]
        return {"executed_count": len(ex), "executed_actions": [r.get("action_display") for r in ex]} if ex else None


def _partie(monkeypatch, tmp_path, fidele):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_MONITEUR", "1")
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    monkeypatch.setenv("CHRYS_HISTORIQUE_FIDELE", "1" if fidele else "0")
    s = _Solveur()
    s.analyzer = _Analyseur()
    _orig = s.step_env

    def step(arguments):  # comme le harnais : le résultat dit ce qui a été joué
        p = _orig(arguments)
        return p | {"action_display": arguments["actions"][0]["action"]}
    s.step_env = step
    from chrysalide.arc3.moteur import MoteurC
    b = branche.creer(s, tmp_path, moteur=MoteurC(budget=1))
    b.en_plan = True  # coups du moteur
    s.step_env({"actions": [{"action": "UP"}]})
    s.step_env({"actions": [{"action": "UP"}]})
    b.en_plan = False
    b._au_modele()  # Franzen reprend la main
    return s.analyzer._last_step_summary, b


def test_resume_decrit_les_coups_du_moteur(monkeypatch, tmp_path):
    r, b = _partie(monkeypatch, tmp_path, True)
    assert r == {"executed_count": 2, "executed_actions": ["UP (auto)", "UP (auto)"]} and b.payloads_auto == []


def test_eteint_resume_inchange(monkeypatch, tmp_path):
    r, _ = _partie(monkeypatch, tmp_path, False)
    assert r == {"executed_actions": ["LEFT"], "executed_count": 1}
