import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from accessibilite_contact import auditer
from enveloppe_contacts import analyser
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger

R = Path(__file__).resolve().parent


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    _m, h, cs, z, _, _ = charger()
    nouveau = np.load(R / "runs/frontiere_bp35_reel2/N2/partie.npz")
    # Deux enveloppes existantes réutilisées ; une vue intermédiaire jamais auditée.
    vues = [
        ("initiale", z["images"][1], R / "runs/enveloppe_contacts_bp35_1/rapport.json"),
        ("finale", nouveau["images"][-1], R / "runs/frontiere_bp35_reel2/enveloppe_nouvelle_vue.json"),
        ("intermediaire", nouveau["images"][6], None),
    ]
    rapport = {"sdk": 0, "vues": {}, "sources": {}}
    for nom, image, cache in vues:
        model = InterventionsElargies(image, h, cs, [3, 4, 6], horizon=8, scene_factory=lambda im, m: decomposer(im, m)[0])
        env = json.loads(cache.read_text()) if cache else analyser(model)
        if cache:
            rapport["sources"][str(cache)] = hashlib.sha256(cache.read_bytes()).hexdigest()
        else:
            (out / "enveloppe_intermediaire.json").write_text(json.dumps(env, indent=2, default=int))
        rapport["vues"][nom] = auditer(model, env)
    rapport["sources"].update(
        {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), R / "accessibilite_contact.py"]}
    )
    (out / "rapport.json").write_text(json.dumps(rapport, indent=2, default=int))
    print(json.dumps({n: {k: v for k, v in r.items() if k != "transits_separateurs"} for n, r in rapport["vues"].items()}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
