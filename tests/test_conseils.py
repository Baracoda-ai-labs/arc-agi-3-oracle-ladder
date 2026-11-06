"""D (CW-422.3 / 422.4) : conseils ajoutés au message de tour de Franzen ; éteint = rien ; témoin à volume égal ; patch."""
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from chrysalide.arc3 import conseils

RACINE = Path(__file__).resolve().parents[1]


def _agent():
    return SimpleNamespace(_last_step_summary=None, _game_elapsed_seconds=0.0,
                           _summarized_knowledge={"world_model": "push the red block onto the cross"})


def _pas(a, **k):
    a._last_step_summary = {"start_action_num": k.pop("debut"), "end_action_num": k.pop("fin"), **k}


def test_eteint_rien(monkeypatch):
    for v in ("CHRYS_NIVEAUX_RESOLUS", "CHRYS_REVUE"):
        monkeypatch.delenv(v, raising=False)
    a = _agent()
    _pas(a, debut=0, fin=1, executed_actions=["UP"], level_transition=True, level=2)
    assert conseils.contexte(a) == "" and not hasattr(a, "_chrys_conseils")


def test_niveaux_resolus_vie_gagnante_et_temoin(monkeypatch):
    monkeypatch.setenv("CHRYS_NIVEAUX_RESOLUS", "1")
    a = _agent()
    _pas(a, debut=0, fin=2, executed_actions=["UP", "UP"])
    assert conseils.contexte(a) == ""
    _pas(a, debut=2, fin=3, executed_actions=["DOWN"], game_over=True)      # vie perdue : oubliée
    conseils.contexte(a)
    _pas(a, debut=3, fin=4, executed_actions=["LEFT"])
    conseils.contexte(a)
    conseils.contexte(a)                                                      # même résumé : compté une fois
    _pas(a, debut=4, fin=5, executed_actions=[{"action": "ACTION6", "x": 3, "y": 7}], level_transition=True, level=2)
    t = conseils.contexte(a)
    assert "Level 1" in t and "push the red block" in t and "winning moves: LEFT, ACTION6(3,7)" in t and "UP" not in t
    monkeypatch.setenv("CHRYS_NIVEAUX_RESOLUS", "2")                          # témoin : même longueur, sans rapport
    b = _agent()
    b.__dict__["_chrys_conseils"] = a._chrys_conseils
    tt = conseils.contexte(b)
    assert len(tt) == len(t) and "push" not in tt and "LEFT" not in tt


def test_revue_une_fois_par_niveau_a_25_pourcent(monkeypatch):
    monkeypatch.setenv("CHRYS_REVUE", "1")
    monkeypatch.setenv("MAX_RUNTIME_MINUTES", "40")                           # 2 400 s : revue à 600 s du niveau
    a = _agent()
    a._game_elapsed_seconds = 500.0
    assert conseils.contexte(a) == ""
    a._game_elapsed_seconds = 610.0
    assert "STRATEGY REVIEW" in conseils.contexte(a)
    a._game_elapsed_seconds = 900.0
    assert conseils.contexte(a) == ""                                         # une seule fois
    _pas(a, debut=0, fin=1, executed_actions=["UP"], level_transition=True, level=2)
    assert conseils.contexte(a) == ""                                         # nouveau niveau : horloge remise
    a._game_elapsed_seconds = 1510.0
    assert "STRATEGY REVIEW" in conseils.contexte(a)


def test_patch_harnais_compatible_et_idempotent(tmp_path):
    h = tmp_path / "ARC3-Inference"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", h / "inference",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for script in ("patcher_inspect.py", "patcher_conseils.py", "patcher_conseils.py"):
        r = subprocess.run([sys.executable, str(RACINE / "scripts/arc3" / script), str(h)], capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr
    agent = h / "inference/agent/tool_agent.py"
    t = agent.read_text()
    assert t.count("CHRYSALIDE-CONSEILS") == 1 and "CHRYSALIDE-INSPECT" in t
    py_compile.compile(str(agent), doraise=True)
    assert (h / "inference/chrysalide_arc3/conseils.py").exists()
