import numpy as np
from garde_oscillations import GardeOscillations
from monde_temporel import Front, ajuster, front_etendu, predire


def test_horloges_restent_ambigues_et_action_inconnue_censuree():
    models = ajuster([(11, 3, 0), (12, 4, -6)])
    assert len(models) == 2
    r = predire(models, Front(8, 53, 20, 60), 3, 13)
    assert r["couvert"] and r["intervalle"] == [53, 53]
    assert predire(models, Front(8, 53, 20, 60), 3, 14)["intervalle"] == [47, 53]
    assert not predire(models, Front(8, 53, 20, 60), ["clic", 0, 0], 13)["couvert"]


def test_front_ignore_hud_sans_couleur_imposee():
    im = np.zeros((64, 64), dtype=int)
    im[50:63, ::2] = 8
    im[-1] = 8
    assert front_etendu(im, 8).haut == 50
    assert front_etendu(im, 7) is None


def test_anti_oscillation_ne_bloque_pas_retrait_ni_information():
    g = GardeOscillations()
    g.enregistrer("k")
    assert g.refuse("k", 4)
    assert not g.refuse("k", 4, gain=1)
    assert not g.refuse("k", 4, retour=True)
    assert not g.refuse("k", 4, progres=True)
    assert not g.refuse("new", 4)


def test_etat_temporel_prevoit_avant_coup_16_sur_archive():
    import json
    from pathlib import Path

    from hypotheses_navigation import HypothesesNavigation
    from monde_temporel import EtatTemporel
    from preflight_interventions_bp35 import charger

    p = Path(__file__).parent / "runs/transfert_N3_bp35_reel2/N3/partie"
    z = np.load(p.with_suffix(".npz"))
    j = json.loads(p.with_suffix(".json").read_text())
    m, _, cs, *_ = charger()
    h = HypothesesNavigation(m)
    state = EtatTemporel(z["images"][0])
    for i, a in enumerate(j["actions"][:15]):
        state.observer(z["images"][i], z["images"][i + 1], a, m)
        h.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
    r = state.evaluer(z["images"][15], m, h, cs, j["actions"][15])
    assert state.rang == 15 and len(state.modeles) == 2
    assert r["prevision"]["intervalle"] == [41, 41]
    assert r["risque"] and not r["admissible"]
