"""Teste une sélection de jumeau visuel avec échange de marqueurs, sans nom de jeu."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / "paquet"), str(ICI)]
from objets_variables import localiser
from roles_observes import PerceptionRoles


def proposer(v, image):
    g = v.vue(image)
    candidats = []
    for m in v.mobiles:
        h, w = m.shape
        x, y = localiser(g, m)
        if np.any(m < 0):
            continue
        for yy in range(64 - h + 1):
            for xx in range(64 - w + 1):
                n = g[yy : yy + h, xx : xx + w]
                d = n != m
                if 0 < d.sum() <= max(1, m.size // 8) and (abs(xx - x) >= w or abs(yy - y) >= h):
                    candidats.append((int(d.sum()), yy, xx, m, d, x, y))
    if not candidats:
        raise ValueError("Pas de jumeau visuel distinct")
    _, yy, xx, m, d, x, y = min(candidats, key=lambda c: c[:3])
    h, w = m.shape
    pred = g.copy()
    a = pred[y : y + h, x : x + w]
    b = pred[yy : yy + h, xx : xx + w]
    vieux = a[d].copy()
    a[d] = b[d]
    b[d] = vieux
    e = {
        "question": "Un clic sur le jumeau visuel échange-t-il le marqueur, ou laisse-t-il la scène inchangée ?",
        "actions": [["clic", xx + w // 2, yy + h // 2]],
        "hud": sorted(map(list, v.hud)),
        "predictions": [
            [
                {"nom": "sans_effet", "image": g.tolist(), "fin": False},
                {"nom": "selection_marqueur_echange", "image": pred.tolist(), "fin": False},
            ]
        ],
        "indices": {"origine": [x, y], "jumeau": [xx, yy], "forme": [h, w], "differences_locales": np.argwhere(d).tolist()},
    }
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    args = ap.parse_args()
    with np.load(args.source.with_suffix(".npz")) as z:
        gs = z["images"].copy()
    actions = [r["action"] for r in json.loads(args.source.with_suffix(".json").read_text())["rows"]]
    v = PerceptionRoles(gs, actions)
    e = proposer(v, gs[-1])
    args.sortie.write_text(json.dumps(e))
    print(json.dumps(e["indices"]))


if __name__ == "__main__":
    main()
