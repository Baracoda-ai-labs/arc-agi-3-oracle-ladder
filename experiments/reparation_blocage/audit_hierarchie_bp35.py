"""Nouvelle perception sur archives, coût et accès distincts ; aucun SDK."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from apprentissage_regles import activation
from boucle_navigation_visible import decalage
from espace_experiences import classer_experiences, partitions
from experience_bfws import ExperienceLocale
from experience_regles_bp35 import cle
from hypotheses_navigation import HypothesesNavigation
from navigation_gravite_visible import NavigationVisible
from perception_hierarchique import contact_observe, decomposer

from chrysalide.langue import depuis_python

R = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sortie", type=Path, required=True)
    out = parser.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    ref = R / "runs/controleur_trois_archives_fige1/bp35"
    j = json.loads((ref / "reference.json").read_text())
    m = NavigationVisible(np.load(ref / "reference.npz")["images"], j["actions"])
    m.cassables = set(j["cassables"])
    m.perception_connexe = True
    mem = json.loads((R / "runs/apprentissage_bp35_reel2/memoire.json").read_text())
    cs = {e["entite"]: {"python": e["valeur"]["python"]} for e in mem["entrees"].values() if e["statut"] == "actif"}
    old = R / "runs/bp35_N2_hypotheses_neuronal_reprise1/N2/partie"
    z = np.load(old.with_suffix(".npz"))
    rows = json.loads(old.with_suffix(".json").read_text())["rows"]
    films = []
    pixel_errors = 0
    for coup in (1, 2):
        before = z["images"][coup - 1]
        _, _, origin = m.lire(before)
        for rank, g in enumerate(z[f"film_{coup}"]):
            dy, err = decalage(before, g, m.palette)
            scene, parents = decomposer(g, m, (origin[0], origin[1] + dy))
            diff = int(np.sum(scene.image()[:-1] != g[:-1]))
            pixel_errors += diff
            actor = next((o for o in scene.sprites if "controle" in o.get("tags", ())), None)
            details = {}
            for n, c in cs.items():
                tag = depuis_python(c["python"])["regles"][0]["quand"][3][2][1]["tag"]
                parts = [o for o in scene.sprites if tag in o.get("tags", ()) and o.get("attrs", {}).get("parent")]
                near = []
                if actor:
                    for p in parts:
                        d = contact_observe(actor, p)
                        if d["distance_pixels"] <= 3:
                            parent = next(o for o in parents if o["nom"] == p["attrs"]["parent"])
                            near.append(
                                {
                                    "parent_type": parent["attrs"]["type_candidat"],
                                    "parent_xy": [parent["x"], parent["y"]],
                                    "tag_partie": tag,
                                    **d,
                                }
                            )
                details[n] = {"active": activation(c["python"], [scene]) is not None, "proches": near}
            films.append(
                {
                    "coup": coup,
                    "frame": rank,
                    "pixels_inexpliques": diff,
                    "camera_dy": dy,
                    "camera_erreur": err,
                    "controle_visible": actor is not None,
                    "regles": details,
                }
            )
    g = z["images"][1]
    scene, parents = decomposer(g, m)
    types = Counter(p["attrs"]["type_candidat"] for p in parents)
    local = HypothesesNavigation(m, clics=(True,))
    local.observer(z["images"][0], rows[0]["action"], g, z["film_1"])
    model = ExperienceLocale(g, local, cs, [3, 4, 6], horizon=6, scene_factory=lambda im, mo: decomposer(im, mo)[0])
    known = {cle(z["images"][i], r["action"]) for i, r in enumerate(rows)}
    for name in ("apprentissage_bp35_reel2",):
        path = R / "runs" / name / "N2/partie"
        pz = np.load(path.with_suffix(".npz"))
        pj = json.loads(path.with_suffix(".json").read_text())
        known.update(cle(pz["images"][i], r["action"]) for i, r in enumerate(pj["rows"]))
    frontier = [(model.depart, [])]
    seen = {model.depart}
    cursor = 0
    exps = []
    while cursor < len(frontier) and cursor < 500:
        state, path = frontier[cursor]
        cursor += 1
        for a in model.actions(state):
            t = model.pas(state, a)
            action = list(a) if isinstance(a, tuple) else a
            newpath = path + [action]
            # Un ancien premier contact n'est pas une nouvelle expérience.
            repeated = cle(g, newpath[0]) in known
            exps.append(
                {
                    "id": len(exps),
                    "actions": newpath,
                    "predictions": dict(zip(cs, t[2], strict=True)),
                    "accessible": not repeated,
                    "cout_actions": len(newpath),
                    "cout_acces": 16,
                    "risque": "modèle partiel, défaite possible",
                }
            )
            if t not in seen:
                seen.add(t)
                frontier.append((t, newpath))
    selection = classer_experiences(exps, cs, 22)
    report = {
        "sdk": 0,
        "films": films,
        "pixels_inexpliques_hors_derniere_ligne": pixel_errors,
        "parents": [
            {
                "type": p["attrs"]["type_candidat"],
                "xy": [p["x"], p["y"]],
                "pixels": p["pixels"].tolist(),
                "couleurs": sorted(set(map(int, p["pixels"][p["pixels"] >= 0]))),
                "occurrences_type": types[p["attrs"]["type_candidat"]],
            }
            for p in parents
        ],
        "hypotheses": cs,
        "experiences": exps,
        "selection": selection,
        "partitions": partitions([[v == "defaite" for v in e["predictions"].values()] for e in exps]),
        "borne": {"horizon": 6, "noeuds": cursor, "tronque": cursor < len(frontier)},
        "sources_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), R / "perception_hierarchique.py", R / "experience_bfws.py"]
        },
    }
    (out / "rapport.json").write_text(json.dumps(report, indent=2, default=int))
    print(
        json.dumps(
            {
                "pixels_inexpliques": pixel_errors,
                "parents": len(parents),
                "types": len(types),
                "transitions": len(exps),
                "classes": report["partitions"]["classes_indiscernables"],
                "choix": selection["choix"],
                "borne": report["borne"],
            }
        )
    )


if __name__ == "__main__":
    main()
