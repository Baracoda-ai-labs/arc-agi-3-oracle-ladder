import json
from pathlib import Path

import numpy as np
from boucle_navigation_visible import decalage
from hypotheses_navigation import HypothesesNavigation
from monde_temporel import EtatTemporel
from plan_phase import HorlogeArchive
from preflight_interventions_bp35 import charger
from sonde_obstacle_contact import proposer


def test_sonde_cible_le_blocage_sans_presumer_son_effet():
    r = Path(__file__).parent / "runs"
    p = r / "route_phase_N3_reel2/N3/partie"
    z = np.load(p.with_suffix(".npz"))
    j = json.loads(p.with_suffix(".json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    t = EtatTemporel(z["images"][0])
    clock = HorlogeArchive(json.loads((r / "horloges_N3_reel1/monde_temporel.json").read_text()))
    for i, a in enumerate(j["actions"]):
        b, after = z["images"][i : i + 2]
        clock.decalage_camera += decalage(b, after, m.palette)[0]
        t.observer(b, after, a, m)
        m.apprendre_clics([b, after], [a])
        h.observer(b, a, after, z[f"film_{i + 1}"])
    im = z["images"][-1]
    initial = im.copy()
    d = proposer(im, h, cs, set(), [3, 4, 6, 7], t, clock, set())
    assert d and len(d["plan"]) == 1
    assert set(d["etapes"][0]["predictions"].values()) == {"inconnue"}
    assert set(d["issues_avant"].values()) == {"defaite"}
    assert set(d["issues_si_retrait"].values()) == {"continue"}
    assert np.array_equal(im, initial)
    assert proposer(im, h, cs, set(), [3, 4, 6, 7], t, clock, {d["type_motif"]}) is None
    assert proposer(im, h, cs, set(), [3, 4, 7], t, clock, set()) is None
    t.rang += 30
    assert proposer(im, h, cs, set(), [3, 4, 6, 7], t, clock, set()) is None
