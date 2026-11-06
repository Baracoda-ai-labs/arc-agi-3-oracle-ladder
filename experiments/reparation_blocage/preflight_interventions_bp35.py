import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from experience_regles_bp35 import cle
from hypotheses_navigation import HypothesesNavigation
from interventions_elargies import InterventionsElargies
from navigation_gravite_visible import NavigationVisible
from perception_hierarchique import decomposer

R = Path(__file__).resolve().parent


def charger():
    ref = R / "runs/controleur_trois_archives_fige1/bp35"
    j = json.loads((ref / "reference.json").read_text())
    m = NavigationVisible(np.load(ref / "reference.npz")["images"], j["actions"])
    m.cassables = set(j["cassables"])
    m.perception_connexe = True
    mem = json.loads((R / "runs/apprentissage_bp35_reel2/memoire.json").read_text())
    cs = {e["entite"]: {"python": e["valeur"]["python"]} for e in mem["entrees"].values() if e["statut"] == "actif"}
    src = R / "runs/bp35_N2_hypotheses_neuronal_reprise1/N2/partie"
    z = np.load(src.with_suffix(".npz"))
    rows = json.loads(src.with_suffix(".json").read_text())["rows"]
    h = HypothesesNavigation(m, clics=(True,))
    h.observer(z["images"][0], rows[0]["action"], z["images"][1], z["film_1"])
    known = {cle(z["images"][i], r["action"]) for i, r in enumerate(rows)}
    src = R / "runs/apprentissage_bp35_reel2/N2/partie"
    pz = np.load(src.with_suffix(".npz"))
    pj = json.loads(src.with_suffix(".json").read_text())
    known.update(cle(pz["images"][i], r["action"]) for i, r in enumerate(pj["rows"]))
    return m, h, cs, z, rows, known


def chercher(image, h, cs, known):
    model = InterventionsElargies(image, h, cs, [3, 4, 6], horizon=8, scene_factory=lambda im, m: decomposer(im, m)[0])
    forbidden = {
        str(list(a) if isinstance(a, tuple) else a)
        for a in model.actions(model.depart)
        if cle(image, list(a) if isinstance(a, tuple) else a) in known
    }
    return model.chercher_minimal(forbidden, max_noeuds=3000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    out = ap.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    _m, h, cs, z, _rows, known = charger()
    r = chercher(z["images"][1], h, cs, known)
    r.update(
        sdk=0,
        cout_acces=16,
        cout_actions=len(r["plan"]) if r["plan"] else None,
        hypotheses=cs,
        source_sha={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), R / "interventions_elargies.py", R / "experience_bfws.py"]
        },
    )
    (out / "rapport.json").write_text(json.dumps(r, indent=2, default=int))
    print(json.dumps({k: v for k, v in r.items() if k not in ("hypotheses", "source_sha")}, default=int))


if __name__ == "__main__":
    main()
