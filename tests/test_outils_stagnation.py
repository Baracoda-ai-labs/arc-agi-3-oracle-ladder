"""CHRYS_OUTILS_APRES : outils de navigation seulement après N coups sans finir le niveau (stagnation). Le compteur est la
VRAIE fonction de Franzen `_priority_action_count`, extraite de son tool_agent.py (sans importer tout le harnais)."""
import ast
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from chrysalide.arc3 import outils_repl as O

RACINE = Path(__file__).resolve().parents[1]
TOOL_AGENT = RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference/agent/tool_agent.py"


def _module_franzen():
    arbre = ast.parse(TOOL_AGENT.read_text())
    fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "_priority_action_count")
    m = types.ModuleType("inference.agent.tool_agent")
    # Code de Franzen versionné dans tiers/ (pas un texte de modèle) : exécuté tel quel pour tester sa vraie fonction.
    exec(compile(ast.Module([fonction], []), str(TOOL_AGENT), "exec"), {"Any": object, **m.__dict__}, m.__dict__)  # noqa: S102
    return m


def test_declenchement_apres_n_coups(monkeypatch):
    m = _module_franzen()
    monkeypatch.setitem(sys.modules, "inference.agent.tool_agent", m)
    monkeypatch.setenv("CHRYS_OUTILS", "1")
    monkeypatch.setenv("CHRYS_OUTILS_APRES", "40")
    agent = SimpleNamespace(_last_step_summary={"end_action_num": 50}, _actions_at_level_start=0)
    assert m._priority_action_count(agent._last_step_summary) == 50  # vraie fonction de Franzen
    assert O.coups_niveau(agent) == 50 and O.outils_actifs(agent)
    agent._actions_at_level_start = 20  # 30 coups seulement dans ce niveau
    assert O.coups_niveau(agent) == 30 and not O.outils_actifs(agent)
    assert O.ligne_tour(agent) == []


def test_sans_seuil_comportement_v2_inchange(monkeypatch):
    monkeypatch.setenv("CHRYS_OUTILS", "1")
    monkeypatch.delenv("CHRYS_OUTILS_APRES", raising=False)
    assert O.outils_actifs(SimpleNamespace())
    monkeypatch.setenv("CHRYS_OUTILS", "0")
    assert not O.outils_actifs(SimpleNamespace())
