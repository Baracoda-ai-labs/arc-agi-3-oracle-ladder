"""Banc sur observations acquises, sans SDK ni sources de jeu."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from boucle_navigation_visible import decalage
from hypotheses_navigation import HypothesesNavigation
from monde_temporel import EtatTemporel
from perception_hierarchique import decomposer
from plan_phase import HorlogeArchive
from preflight_interventions_bp35 import charger
from support_planificateur import InterventionsSupports, chercher

R = Path(__file__).parent / "runs"


def preparer():
    m, _, cs, *_ = charger()
    source = R / "route_phase_N3_reel2/N3/partie"
    z = np.load(source.with_suffix(".npz"))
    j = json.loads(source.with_suffix(".json").read_text())
    h = HypothesesNavigation(m)
    for i, a in enumerate(j["actions"]):
        b, c = z["images"][i : i + 2]
        m.apprendre_clics([b, c], [a])
        h.observer(b, a, c, z[f"film_{i + 1}"])
    regle = json.loads((R / "refermeture_N3_reel1/support_reversible.json").read_text())
    return m, h, cs, z, j, regle


def modele(image, h, cs, regle, actif=True, camera=0, horizon=10):
    return InterventionsSupports(
        image,
        h,
        cs,
        [3, 4, 6, 7],
        supports=[regle] if actif else [],
        contexte=regle["contexte"],
        camera_dy=camera,
        horizon=horizon,
        scene_factory=lambda im, m: decomposer(im, m)[0],
    )


def main(out):
    out.mkdir(exist_ok=False)
    m, h, cs, z, j, regle = preparer()
    result = {}
    for name, n in [("avant_ouverture", 3), ("ouvert", 4), ("nouvelle_zone", 7)]:
        t = EtatTemporel(z["images"][0])
        clock = HorlogeArchive(json.loads((R / "horloges_N3_reel1/monde_temporel.json").read_text()))
        for i, a in enumerate(j["actions"][:n]):
            b, c = z["images"][i : i + 2]
            clock.decalage_camera += decalage(b, c, m.palette)[0]
            t.observer(b, c, a, m)
        pair = {}
        for actif in (False, True):
            model = modele(z["images"][n], h, cs, regle, actif, clock.decalage_camera)
            report = chercher(model, clock, t)
            pair["actif" if actif else "inactif"] = report
        positions = lambda r: {tuple(x["position"]) for x in r["atteints"]}
        new = positions(pair["actif"]) - positions(pair["inactif"])
        result[name] = {
            "nouveaux_arrets": sorted(new),
            "actif": {k: v for k, v in pair["actif"].items() if k != "atteints"},
            "inactif": {k: v for k, v in pair["inactif"].items() if k != "atteints"},
        }
        (out / f"{name}.json").write_text(json.dumps(pair, indent=2, default=int))
    result["sdk"] = 0
    result["coups_reels"] = 0
    result["conclusion"] = "Cycle raccordé ; points d’arrêt nouveaux à lire par vue, aucune victoire présumée."
    (out / "rapport.json").write_text(json.dumps(result, indent=2, default=int))
    sources = [
        Path(__file__),
        Path(__file__).with_name("support_planificateur.py"),
        R / "refermeture_N3_reel1/support_reversible.json",
    ]
    (out / "sources.json").write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2))
    print(json.dumps(result, default=int))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
