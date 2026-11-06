import json
from pathlib import Path

import numpy as np
from hypotheses_navigation import HypothesesNavigation
from monde_temporel import EtatTemporel
from plan_phase import HorlogeArchive, decision
from preflight_interventions_bp35 import charger

R = Path(__file__).parent / "runs"


def test_phase_reproduit_bords_et_compte_chaque_action():
    clock = HorlogeArchive(json.loads((R / "horloges_N3_reel1/monde_temporel.json").read_text()))
    assert [clock.bord(i) for i in (12, 13, 14, 15, 16)] == [53, 53, 47, 47, 41]


def test_surface_inconnue_pas_transformee_en_passage():
    z = np.load(R / "horloges_N3_reel1/N3/partie.npz")
    j = json.loads((R / "horloges_N3_reel1/N3/partie.json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    t = EtatTemporel(z["images"][0])
    for i, a in enumerate(j["actions"][:3]):
        t.observer(z["images"][i], z["images"][i + 1], a, m)
        h.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
    clock = HorlogeArchive(json.loads((R / "horloges_N3_reel1/monde_temporel.json").read_text()))
    pz = np.load(R / "remontee_bp35_reel1/N2/partie.npz")
    colors = set(map(int, np.unique(pz["images"][:-1])))
    d = decision(z["images"][3], h, cs, set(), 10, [3, 4, 6, 7], None, t, clock, colors, set())
    assert len(d["plan"]) == 1 and d["raison"] == "sonde_classe_visuelle_nouvelle"
    assert set(d["etapes"][0]["predictions"].values()) == {"inconnue"}
    assert d["marge_pixels"] > 0
    # Même lieu, phase tardive : le budget temporel ne permet plus cette sonde.
    t.rang = 16
    blocked = decision(z["images"][3], h, cs, set(), 2, [3, 4, 6, 7], None, t, clock, colors, set())
    assert blocked["plan"] is None


def test_ouverture_observee_transmise_a_navigation_et_route():
    z = np.load(R / "route_phase_N3_reel1/N3/partie.npz")
    j = json.loads((R / "route_phase_N3_reel1/N3/partie.json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    t = EtatTemporel(z["images"][0])
    for i, a in enumerate(j["actions"]):
        t.observer(z["images"][i], z["images"][i + 1], a, m)
        m.apprendre_clics([z["images"][i], z["images"][i + 1]], [a])
        h.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
    assert all(h.catalogue[n][1] for n in h.actives())
    clock = HorlogeArchive(json.loads((R / "horloges_N3_reel1/monde_temporel.json").read_text()))
    colors = set(map(int, np.unique(np.load(R / "remontee_bp35_reel1/N2/partie.npz")["images"][:-1])))
    d = decision(z["images"][-1], h, cs, set(), 10, [3, 4, 6, 7], None, t, clock, colors, set())
    assert d["raison"] == "route_phase" and len(d["plan"]) == 3
    assert min(s["marge_pixels"] for s in d["etapes"]) > 0
    assert len(set(map(tuple, d["etapes"][-1]["positions"]))) > 1


def test_camera_recale_front_avant_apparition():
    clock = HorlogeArchive(json.loads((R / "horloges_N3_reel1/monde_temporel.json").read_text()))
    z = np.load(R / "route_phase_N3_reel2/N3/partie.npz")
    t = EtatTemporel(z["images"][0])
    t.rang = 7
    original = clock.prevoir(t, 1)
    clock.decalage_camera = 24
    assert clock.prevoir(t, 1) == original + 24
    assert clock.prevoir(t, 2) - clock.prevoir(t, 1) == 0
