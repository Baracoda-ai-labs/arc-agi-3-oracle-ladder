"""Diagnostic hors jeu du nouvel embranchement, sans accès aux sources ARC."""

import json
from pathlib import Path

import numpy as np
from boucle_navigation_visible import decalage
from hypotheses_navigation import HypothesesNavigation
from interventions_elargies import InterventionsElargies
from monde_temporel import EtatTemporel
from perception_hierarchique import decomposer
from plan_phase import HorlogeArchive, decision
from preflight_interventions_bp35 import charger

R = Path(__file__).parent / "runs"


def main():
    p = R / "route_phase_N3_reel2"
    z = np.load(p / "N3/partie.npz")
    j = json.loads((p / "N3/partie.json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    t = EtatTemporel(z["images"][0])
    clock = HorlogeArchive(json.loads((R / "horloges_N3_reel1/monde_temporel.json").read_text()))
    for i, a in enumerate(j["actions"]):
        before, after = z["images"][i : i + 2]
        clock.decalage_camera += decalage(before, after, m.palette)[0]
        t.observer(before, after, a, m)
        m.apprendre_clics([before, after], [a])
        h.observer(before, a, after, z[f"film_{i + 1}"])
    colors = set(map(int, np.unique(np.load(R / "remontee_bp35_reel1/N2/partie.npz")["images"][:-1])))
    result = decision(z["images"][-1], h, cs, set(), 33, [3, 4, 6, 7], None, t, clock, colors, set())
    native = InterventionsElargies(
        z["images"][-1], h, cs, [3, 4, 6, 7], horizon=10, scene_factory=lambda im, m: decomposer(im, m)[0]
    )
    result["actions_locales"] = [
        {"action": a, "position_et_issues": native.pas(native.depart, a)} for a in native.actions(native.depart)
    ]
    result["decalage_camera"] = clock.decalage_camera
    result["hypotheses_navigation"] = h.actives()
    result["victoire_sdk"] = j["victory"]
    result["sdk_appels"] = 0
    result["portee"] = "rejet par hypothèses natives, pas preuve que toute autre route est mortelle"
    out = R / "route_phase_N3_diagnostic"
    out.mkdir(exist_ok=False)
    (out / "rapport.json").write_text(
        json.dumps(result, indent=2, default=lambda x: sorted(x) if isinstance(x, frozenset) else int(x))
    )
    print(json.dumps({k: v for k, v in result.items() if k != "actions_locales"}))


if __name__ == "__main__":
    main()
