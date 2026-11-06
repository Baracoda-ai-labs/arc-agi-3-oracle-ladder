"""Recherche de reclics sur une ouverture conservée dans les seules archives autorisées."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from boucle_navigation_visible import decalage
from preflight_interventions_bp35 import charger

R = Path(__file__).parent / "runs"


def main(out):
    out.mkdir(exist_ok=False)
    m, *_ = charger()
    paths = [R / "publics_ref_g0/bp35/N1/partie.json"]
    for d in sorted(R.iterdir()):
        if d.is_dir() and (
            "bp35" in d.name or d.name.startswith(("route_phase_N3", "contact_N3", "horloges_N3", "annulation_N3"))
        ):
            paths.extend(sorted(d.glob("N*/partie.json")))
    hits = []
    sources = {}
    clicks = 0
    for p in paths:
        j = json.loads(p.read_text())
        z = np.load(p.with_suffix(".npz"))
        opened = {}
        camera = 0
        for f in [p, p.with_suffix(".npz")]:
            sources[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
        for i, a in enumerate(j["actions"]):
            before, after = z["images"][i : i + 2]
            dy, err = decalage(before, after, m.palette)
            if err > 0.15:
                opened = {}
            if isinstance(a, list):
                clicks += 1
                key = (a[1] // m.pas, (a[2] - camera) // m.pas)
                if key in opened and before[a[2], a[1]] == m.sol:
                    hits.append({"source": str(p), "rang": i + 1, "action": a, "ouverture_precedente": opened[key]})
                if dy == 0 and err <= 0.15:
                    mask = before[:-1] != after[:-1]
                    if 0 < mask.sum() <= 2 * m.pas**2 and np.mean(after[:-1][mask] == m.sol) > 0.7:
                        opened[key] = {"rang": i + 1, "couleur": int(Counter(before[:-1][mask].tolist()).most_common(1)[0][0])}
            elif a in (0, 7):
                opened = {}
            camera += dy
    report = {
        "archives": len(paths),
        "clics_lus_avec_reprises": clicks,
        "reclics_detectes": hits,
        "limite": "repérage sur grille recalée, remise à zéro après retour/reset/caméra incertaine ; pas preuve exhaustive de toutes les expériences possibles",
        "sdk": 0,
    }
    (out / "rapport.json").write_text(json.dumps(report, indent=2))
    (out / "sources.json").write_text(json.dumps(sources, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
