import shutil
from dataclasses import dataclass
from pathlib import Path

from chrysalide.arc3 import consignes as cs

RACINE = Path(__file__).resolve().parents[1]
FRANZEN = RACINE / "tiers/arc-agi-3-solution/ARC3-Inference"
INTERRUPTEURS = ("CHRYS_EPINGLE", "CHRYS_AUDIT", "CHRYS_LIBELLES", "CHRYS_AUDIT_PREDIRE", "CHRYS_AUDIT_ETAPES")


@dataclass
class Frame:
    level: int


@dataclass
class H:
    action: str
    frame: Frame


class Agent:
    def __init__(self):
        prompts = (FRANZEN / "inference/agent/prompts.py").read_text()
        i = prompts.find("If you identify such a bar")
        self._system_prompt = "SYS " + prompts[i:i + 300]
        self._history_messages = [{"role": "assistant", "content": "World model: push red block onto the X"}]


def eteindre(mp):
    for n in INTERRUPTEURS:
        mp.delenv(n, raising=False)


def test_eteint_ne_change_rien(monkeypatch):
    eteindre(monkeypatch)
    a = Agent()
    avant = a._system_prompt
    for niv in (1, 1, 2, 2, 3):
        assert cs.tour(a, niv, [H("UP", Frame(1))]) == []
    assert a._system_prompt == avant and not hasattr(a, "_chrys_consignes")


def test_epingle_au_niveau_resolu(monkeypatch):
    eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_EPINGLE", "1")
    a = Agent()
    hist = [H(f"A{i}", Frame(1)) for i in range(40)] + [H("B", Frame(2))]
    cs.tour(a, 1, hist[:5])
    cs.tour(a, 2, hist)
    cs.tour(a, 2, hist)
    assert a._system_prompt.count("Level 1 solved") == 1
    assert "A10, A11" in a._system_prompt and "A9," not in a._system_prompt  # 30 dernières seulement
    assert "push red block onto the X" in a._system_prompt


def test_audit_une_fois_par_niveau(monkeypatch):
    eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_AUDIT", "1")
    monkeypatch.setenv("CHRYS_AUDIT_ETAPES", "3")
    monkeypatch.setenv("CHRYS_AUDIT_PREDIRE", "1")
    a = Agent()
    sorties = [cs.tour(a, 1, []) for _ in range(6)]
    assert [len(s) for s in sorties] == [0, 0, 0, 1, 0, 0]
    assert "STRATEGY AUDIT" in sorties[3][0] and "chrys_verifier" in sorties[3][0]
    assert [len(cs.tour(a, 2, [])) for _ in range(5)] == [0, 0, 0, 1, 0]


def test_libelles_remplace_la_consigne_de_franzen(monkeypatch):
    eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_LIBELLES", "1")
    a = Agent()
    assert cs.BARRE_FRANZEN.search(a._system_prompt)
    cs.tour(a, 1, [])
    assert not cs.BARRE_FRANZEN.search(a._system_prompt) and cs.BARRE_HONNETE in a._system_prompt


def test_patcher_ancre_unique_et_idempotent(tmp_path):
    from scripts.arc3.patcher_consignes import ANCRE, MARQUE, patcher
    src = FRANZEN / "inference/agent/tool_agent.py"
    assert src.read_text().count(ANCRE) == 1
    copie = tmp_path / "ARC3-Inference"
    (copie / "inference/agent").mkdir(parents=True)
    shutil.copy(src, copie / "inference/agent/tool_agent.py")
    assert patcher(copie) == "patché"
    assert patcher(copie) == "déjà patché"
    assert (copie / "inference/agent/tool_agent.py").read_text().count(MARQUE) == 1
