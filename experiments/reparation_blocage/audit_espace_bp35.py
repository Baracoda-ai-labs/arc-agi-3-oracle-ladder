"""Analyse nouvelle des films déjà payés ; aucun jeu exécuté."""

import argparse
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import activation
from espace_experiences import partitions, tuiles_multicolores
from experience_bfws import ExperienceLocale
from hypotheses_navigation import HypothesesNavigation
from issues_observees import scene_image
from navigation_gravite_visible import NavigationVisible

from chrysalide.arc3.langage import Programme
from chrysalide.langue import depuis_python

R = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sortie", type=Path, required=True)
    out = parser.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    ref = R / "runs/controleur_trois_archives_fige1/bp35"
    meta = json.loads((ref / "reference.json").read_text())
    m = NavigationVisible(np.load(ref / "reference.npz")["images"], meta["actions"])
    m.cassables = set(meta["cassables"])
    m.perception_connexe = True
    mem = json.loads((R / "runs/apprentissage_bp35_reel2/memoire.json").read_text())
    cs = {
        entry["entite"]: {"python": entry["valeur"]["python"]} for entry in mem["entrees"].values() if entry["statut"] == "actif"
    }
    ids = list(cs)
    old = R / "runs/bp35_N2_hypotheses_neuronal_reprise1/N2/partie"
    z = np.load(old.with_suffix(".npz"))
    rows = json.loads(old.with_suffix(".json").read_text())["rows"]
    g = z["images"][1]
    scene = scene_image(g, m)
    actor = next(o for o in scene.sprites if "controle" in o.get("tags", ()))
    programmes = {n: Programme(depuis_python(c["python"])) for n, c in cs.items()}
    h, w = actor["pixels"].shape
    points = []
    matrix = []
    for y in range(63 - h + 1):
        for x in range(64 - w + 1):
            actor["x"], actor["y"] = x, y
            pred = []
            for p in programmes.values():
                scene.issue = None
                p.step(scene, ("OBSERVE",))
                pred.append(scene.issue == "defaite")
            points.append((x, y))
            matrix.append(pred)
    frames = []
    for coup in (1, 2):
        for i, frame in enumerate(z[f"film_{coup}"]):
            sc = scene_image(frame, m)
            frames.append(
                {
                    "coup": coup,
                    "frame": i,
                    "controle_visible": any("controle" in o.get("tags", ()) for o in sc.sprites),
                    "activation": [activation(c["python"], [sc]) is not None for c in cs.values()],
                }
            )
    local = HypothesesNavigation(m, clics=(True,))
    local.observer(z["images"][0], rows[0]["action"], g, z["film_1"])
    model = ExperienceLocale(g, local, cs, [3, 4, 6], horizon=6)
    # Cartographie complète du petit graphe existant, pas répétition d'une partie.
    frontier = [(model.depart, [])]
    seen = {model.depart}
    trans = []
    cursor = 0
    while cursor < len(frontier) and cursor < 500:
        s, path = frontier[cursor]
        cursor += 1
        for a in model.actions(s):
            t = model.pas(s, a)
            trans.append({"actions": path + [a], "issues": list(t[2]), "position": list(t[0])})
            if t not in seen:
                seen.add(t)
                frontier.append((t, path + [a]))
    reachable = [[v == "defaite" for v in t["issues"]] for t in trans]
    motifs = tuiles_multicolores(g, m)
    report = {
        "ids": ids,
        "geometrie": partitions(matrix),
        "films": frames,
        "actions_accessibles": partitions(reachable),
        "transitions": trans,
        "motifs": motifs,
        "borne": {"horizon": 6, "noeuds": cursor, "tronque": cursor < len(frontier)},
        "sdk": 0,
        "avertissement": "positions géométriques ne sont pas des états accessibles ; poids uniformes non calibrés",
    }
    (out / "rapport.json").write_text(json.dumps(report, indent=2))
    np.savez_compressed(out / "matrice.npz", points=np.array(points), predictions=np.array(matrix), ids=np.array(ids))
    print(
        json.dumps(
            {
                "geometrie_classes": report["geometrie"]["classes_indiscernables"],
                "actions_classes": report["actions_accessibles"]["classes_indiscernables"],
                "transitions": len(trans),
                "motifs_multicolores": len(motifs),
                "borne": report["borne"],
            }
        )
    )


if __name__ == "__main__":
    main()
