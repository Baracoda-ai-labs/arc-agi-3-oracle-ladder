import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from boucle_navigation_visible import decalage
from garde_oscillations import GardeOscillations, signature
from hypotheses_navigation import HypothesesNavigation
from monde_temporel import ajuster, front_etendu, predire, risque_contact
from preflight_interventions_bp35 import charger

R = Path(__file__).resolve().parent


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    source = R / "runs/transfert_N3_bp35_reel2/N3/partie"
    z = np.load(source.with_suffix(".npz"))
    j = json.loads(source.with_suffix(".json").read_text())
    m, _, cs, *_ = charger()
    baseline = set(map(int, np.unique(z["images"][0][:-1])))
    candidate = None
    onset = None
    for i, g in enumerate(z["images"][1:], 1):
        news = set(map(int, np.unique(g[:-1]))) - baseline
        for c in sorted(news):
            f = front_etendu(g, c)
            if f.largeur >= g.shape[1] // 2 and f.pixels >= g.shape[1]:
                candidate = c
                onset = i
                break
        if candidate is not None:
            break
    if candidate is None:
        raise ValueError("Aucun front nouveau étendu")
    fronts = [front_etendu(g, candidate) for g in z["images"]]
    learning_end = onset + 2
    train = [(i, j["actions"][i - 1], fronts[i].haut - fronts[i - 1].haut) for i in range(onset + 1, learning_end + 1)]
    models = ajuster(train)
    validation = []
    h = HypothesesNavigation(m)
    # Catalogue de navigation compatible juste avant test final : ouvert, pas vérité imposée.
    for name in list(h.actives()):
        if name not in ["g-1_clic1", "g0_clic1"]:
            h.atms.interdire([name])
    for i in range(learning_end + 1, len(fronts)):
        forecast = predire(models, fronts[i - 1], j["actions"][i - 1], i)
        risk = (
            risque_contact(z["images"][i - 1], m, h, cs, fronts[i - 1], forecast["intervalle"], j["actions"][i - 1])
            if forecast["couvert"]
            else None
        )
        validation.append(
            {
                "coup": i,
                "prediction_avant_observation": forecast,
                "haut_observe": fronts[i].haut,
                "statique_erreur": abs(fronts[i].haut - fronts[i - 1].haut),
                "risque_projete": risk,
            }
        )
    guard = GardeOscillations()
    dyn = HypothesesNavigation(m)
    audit = []
    for i, a in enumerate(j["actions"]):
        decision = (
            R / "runs/transfert_N3_bp35_reel2" / f"decision_avant_{i - 4}.json"
            if i >= 5
            else R / "runs/transfert_N3_bp35_reel1" / f"decision_avant_{i + 1}.json"
        )
        d = json.loads(decision.read_text())
        key = signature(z["images"][i], m, a, dyn.actives())
        rejected = guard.refuse(key, a, d.get("gain_minimax", 0))
        guard.enregistrer(key)
        audit.append({"coup": i + 1, "action": a, "gain_annonce": d.get("gain_minimax", 0), "refus_contrefactuel": rejected})
        if i < 15:
            dyn.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
    films = []
    for i in range(onset, len(fronts)):
        vals = [front_etendu(g, candidate) for g in z[f"film_{i}"]]
        films.append(
            {
                "coup": i,
                "action": j["actions"][i - 1],
                "fronts": [asdict(v) if v else None for v in vals],
                "camera_dy": decalage(z["images"][i - 1], z["images"][i], m.palette)[0],
            }
        )
    report = {
        "sdk": 0,
        "caracteristique": "nouvelle couleur étendue, groupement visuel hypothétique",
        "couleur_inferee": candidate,
        "premiere_apparition": onset,
        "fin_apprentissage": learning_end,
        "transitions_apprentissage": train,
        "modeles": models,
        "validation_chronologique": validation,
        "films": films,
        "garde_oscillations": audit,
        "limite": "choix du descripteur après inspection humaine ; validation chronologique sur traces, pas évaluation indépendante",
        "sources": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                source.with_suffix(".json"),
                source.with_suffix(".npz"),
                Path(__file__),
                R / "monde_temporel.py",
                R / "garde_oscillations.py",
            ]
        },
    }
    (out / "rapport.json").write_text(json.dumps(report, indent=2, default=int))
    print(
        json.dumps(
            {
                "onset": onset,
                "models": models,
                "validation": [
                    (r["coup"], r["prediction_avant_observation"]["intervalle"], r["haut_observe"], r["risque_projete"]["risque"])
                    for r in validation
                ],
                "refus_cycles": [r["coup"] for r in audit if r["refus_contrefactuel"]],
            }
        )
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
