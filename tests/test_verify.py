"""T0.5 : vérificateurs (extraction stricte, types, pytest isolé, contraintes)."""
import json

import pytest

from chrysalide.verify import core
from chrysalide.verify.core import verify

INT = {"verifier_id": "json_int", "expected": 246}
STR = {"verifier_id": "json_str", "expected": "Zadrouk Glaidrous"}
CODE = {"verifier_id": "pytest_fn", "expected": {"fonction": "f", "tests": [[0, 1], [5, 11]]}}
J = lambda v: json.dumps({"reponse": v})


@pytest.mark.parametrize("out,status", [
    ('{"reponse": 246}', "correct"),
    ('  ```json\n{"reponse": 246}\n```  ', "correct"),
    ('<think>\n{"reponse": 1}\n</think>\n{"reponse": 246}', "correct"),
    ('{"reponse": 247}', "incorrect"),
    ('{"reponse": "246"}', "unextractable"),
    ('{"reponse": 246.0}', "unextractable"),
    ('{"reponse": true}', "unextractable"),
    ('{"reponse": 246, "reponse": 1}', "unextractable"),
    ('{"reponse": 246}\n{"reponse": 1}', "unextractable"),
    ('Réponse : {"reponse": 246}', "unextractable"),
    ('{"reponse": 246, "note": 1}', "unextractable"),
])
def test_int(out, status):
    assert verify(INT, out).status == status


def test_str_normalisation():
    assert verify(STR, J(" zadrouk  glaidrous ")).status == "correct"
    assert verify(STR, J("Zadrouk Glaidrou")).status == "incorrect"
    assert verify(STR, J("")).status == "unextractable"


def test_code():
    ok = "def f(x):\n    return 2 * x + 1\n"
    assert verify(CODE, J(ok)).status == "correct"
    assert verify(CODE, J("def f(x):\n    return x\n")).status == "incorrect"
    assert verify(CODE, J("def f(x):\n    return (\n")).status == "incorrect"  # erreur de syntaxe = échec des tests
    assert verify(CODE, J("def g(x):\n    return 2 * x + 1\n")).status == "unextractable"
    assert verify(CODE, J(ok + "\n" + ok)).status == "unextractable"  # deux définitions = contradiction


def test_code_timeout(monkeypatch):
    monkeypatch.setattr(core, "TIMEOUT_S", 2)
    v = verify(CODE, J("def f(x):\n    while True:\n        pass\n"))
    assert v.status == "incorrect" and v.details.get("raison") in ("timeout", None)


def test_code_isole_du_depot():
    """Le candidat tourne dans un dossier temporaire en mode isolé : il ne voit pas le paquet chrysalide."""
    code = "import chrysalide\ndef f(x):\n    return 2 * x + 1\n"
    assert verify(CODE, J(code)).status == "incorrect"


def test_contraintes():
    t = {**INT, "constraints": {"forbidden_tools": ["T9"], "max_tool_calls": 2, "max_tokens": 100}}
    good = '{"reponse": 246}'
    assert verify(t, good, {"tool_calls": [{"tool": "T1"}], "tokens": 50}).status == "correct"
    assert verify(t, good, {"tool_calls": [{"tool": "T9"}]}).status == "constraint_violation"
    assert verify(t, good, {"tool_calls": [{"tool": "T1"}] * 3}).status == "constraint_violation"
    assert verify(t, good, {"tokens": 101}).status == "constraint_violation"
    assert verify(INT, good, {"tool_calls": [{"tool": "T9"}]}).status == "correct"  # pas de contrainte déclarée
