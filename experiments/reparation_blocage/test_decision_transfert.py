from pathlib import Path

import numpy as np
from decision_transfert import decision
from hypotheses_navigation import HypothesesNavigation
from preflight_interventions_bp35 import charger


def test_n3_ouvre_six_dynamiques_sans_solution():
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    root = Path(__file__).parent
    image = np.load(root / "runs/remontee_bp35_reel1/N2/partie.npz")["images"][-1]
    d = decision(image, h, cs, set(), 40, [3, 4, 6, 7])
    assert len(h.actives()) == 6 and d["gain_minimax"] > 0
    assert len(d["checks"]) == 6
    assert all(v == "continue" for checks in d["checks"].values() for v in checks.values())


def test_clic_distant_reutilise_interventions_elargies():
    import json

    from experience_regles_bp35 import cle

    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    root = Path(__file__).parent / "runs/transfert_N3_bp35_reel1/N3/partie"
    z = np.load(root.with_suffix(".npz"))
    j = json.loads(root.with_suffix(".json").read_text())
    known = set()
    for i, a in enumerate(j["actions"]):
        h.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
        known.add(cle(z["images"][i], a))
    d = decision(z["images"][-1], h, cs, known, 35, [3, 4, 6, 7])
    assert d["gain_minimax"] > 0 and isinstance(d["plan"][0], list)
    assert cle(z["images"][-1], d["plan"][0]) not in known
