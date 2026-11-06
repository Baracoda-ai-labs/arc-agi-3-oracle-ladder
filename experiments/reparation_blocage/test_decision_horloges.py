import json
from pathlib import Path

import numpy as np
from decision_horloges import decision
from experience_regles_bp35 import cle
from hypotheses_navigation import HypothesesNavigation
from monde_temporel import EtatTemporel
from preflight_interventions_bp35 import charger


def test_experience_horloges_nouvelle_et_sans_contact_predit():
    p = Path(__file__).parent / "runs/transfert_N3_bp35_reel2/N3/partie"
    z = np.load(p.with_suffix(".npz"))
    j = json.loads(p.with_suffix(".json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    t = EtatTemporel(z["images"][0])
    known = set()
    for i, a in enumerate(j["actions"][:12]):
        t.observer(z["images"][i], z["images"][i + 1], a, m)
        h.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
        known.add(cle(z["images"][i], a))
    d = decision(z["images"][12], h, cs, known, 28, [3, 4, 6, 7], temporel=t)
    assert d["raison"] == "departage_horloges"
    assert d["predictions_front"] == {"action": 47, "phase_2": 53}
    assert not d["controle_temporel"]["risque"]


def test_observation_prospective_refute_action_et_bloque_contact():
    p = Path(__file__).parent / "runs/horloges_N3_reel1/N3/partie"
    z = np.load(p.with_suffix(".npz"))
    j = json.loads(p.with_suffix(".json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m, clics=(False, True))
    t = EtatTemporel(z["images"][0])
    for i, action in enumerate(j["actions"]):
        obs = t.observer(z["images"][i], z["images"][i + 1], action, m)
        h.observer(z["images"][i], action, z["images"][i + 1], z[f"film_{i + 1}"])
        if i == 12:
            assert obs["front"]["haut"] == 53
            assert [x["type"] for x in obs["modeles"]] == ["phase_2"]
    assert not j["victory"]
    for action in (4, ["clic", 51, 33]):
        check = t.evaluer(z["images"][-1], m, h, cs, action)
        assert check["risque"] and not check["admissible"]
