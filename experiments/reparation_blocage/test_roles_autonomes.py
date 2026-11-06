import json
from pathlib import Path

import numpy as np
import pytest
from boucle_roles_autonome import comparer, decider

R = Path(__file__).parent / "ka59_roles"


@pytest.mark.parametrize("n,branche", [(8, "roles_puis_selection"), (11, "roles_puis_selection"), (32, "selection_contact")])
def test_decision_depuis_prefixe_seul(tmp_path, n, branche):
    z = np.load(R / "session/N1/partie.npz")
    rows = json.loads((R / "session/N1/partie.json").read_text())["rows"][:n]
    source = tmp_path / "prefixe"
    source.with_suffix(".json").write_text(json.dumps({"rows": [{"action": r["action"]} for r in rows]}))
    np.savez(source.with_suffix(".npz"), images=z["images"][: n + 1], **{f"film_{k}": z[f"film_{k}"] for k in range(1, n + 1)})
    exp = decider(source, tmp_path / "decision", [1, 2, 3, 4, 6])
    assert exp is not None
    e = json.loads(exp.read_text())
    assert e["actions"] and len(e["actions"]) == len(e["predictions"])
    decision = json.loads((tmp_path / "decision/decision.json").read_text())
    assert decision["branche"] == branche
    assert decision["historique_actions"] == n
    if n == 11:
        assert e["actions"][0][0] == "clic"
    if n == 32:
        controles = json.loads((tmp_path / "decision/candidats/controles.json").read_text())
        assert [r["nom"] for r in controles if not r.get("refute")] == ["sortie"]
        assert len(e["actions"]) == 7


def test_terminal_exige_confirmation_sdk_et_frame():
    image = np.zeros((2, 2), int)
    autre = np.ones((2, 2), int)
    preds = [{"nom": "h", "image": image.tolist(), "fin": True}]
    assert comparer(preds, autre, [image, autre], [], True)[0]["conforme"]
    assert not comparer(preds, autre, [image, autre], [], False)[0]["conforme"]
    assert not comparer(preds, autre, [autre], [], True)[0]["conforme"]


def test_pas_de_clic_non_offert(tmp_path):
    z = np.load(R / "session/N1/partie.npz")
    n = 11
    rows = json.loads((R / "session/N1/partie.json").read_text())["rows"][:n]
    source = tmp_path / "prefixe"
    source.with_suffix(".json").write_text(json.dumps({"rows": rows}))
    np.savez(source.with_suffix(".npz"), images=z["images"][: n + 1], **{f"film_{k}": z[f"film_{k}"] for k in range(1, n + 1)})
    exp = decider(source, tmp_path / "decision", [1, 2, 3, 4])
    if exp is not None:
        assert all(isinstance(a, int) and a in (1, 2, 3, 4) for a in json.loads(exp.read_text())["actions"])
