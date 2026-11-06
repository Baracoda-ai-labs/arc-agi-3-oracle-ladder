"""Couverture des opérateurs et route permissive non exécutable, sur films seuls."""

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path

import numpy as np
from boucle_navigation_visible import decalage
from enveloppe_contacts import analyser
from hypotheses_navigation import HypothesesNavigation
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger

R = Path(__file__).parent / "runs"


def main(out):
    out.mkdir(exist_ok=False)
    m, _, cs, *_ = charger()
    paths = [R / "publics_ref_g0/bp35/N1/partie.json"]
    for d in sorted(R.iterdir()):
        if d.is_dir() and ("bp35" in d.name or d.name.startswith(("route_phase_N3", "contact_N3", "horloges_N3"))):
            paths.extend(sorted(d.glob("N*/partie.json")))
    seen = set()
    records = []
    sources = {}
    duplicates = 0
    for p in paths:
        j = json.loads(p.read_text())
        z = np.load(p.with_suffix(".npz"))
        sources[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        sources[str(p.with_suffix(".npz"))] = hashlib.sha256(p.with_suffix(".npz").read_bytes()).hexdigest()
        for i, a in enumerate(j["actions"]):
            before, after = z["images"][i : i + 2]
            key = (j["level"], before[:-1].tobytes(), str(a), after[:-1].tobytes())
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            record = {"archive": str(p), "rang": i + 1, "niveau": j["level"], "action": a}
            try:
                dy, err = decalage(before, after, m.palette)
                bpos = m.position(before)
                apos = m.position(after)
                record.update(
                    camera=dy,
                    erreur_camera=err,
                    position_avant=bpos,
                    position_apres=apos,
                    deplacement_recale=[apos[0] - bpos[0], apos[1] - bpos[1] - dy],
                )
                if a == 7 and i > 0:
                    old = z["images"][i - 1]
                    record.update(
                        action_precedente=j["actions"][i - 1],
                        restauration_exacte=bool(np.array_equal(old[:-1], after[:-1])),
                        position_modifiee_avant_retour=m.position(old) != bpos,
                    )
            except (ValueError, IndexError) as e:
                record["non_comparable"] = str(e)
            records.append(record)
    p = R / "contact_N3_reel1/N3/partie"
    z = np.load(p.with_suffix(".npz"))
    j = json.loads(p.with_suffix(".json").read_text())
    h = HypothesesNavigation(m)
    for i, a in enumerate(j["actions"]):
        b, c = z["images"][i : i + 2]
        m.apprendre_clics([b, c], [a])
        h.observer(b, a, c, z[f"film_{i + 1}"])
    model = InterventionsElargies(
        z["images"][-1], h, cs, [3, 4, 6, 7], horizon=12, scene_factory=lambda im, m: decomposer(im, m)[0]
    )
    env = analyser(model)
    adjacency = {}
    for edge in env.get("aretes", []):
        if all(v == "continue" for v in edge["issues"].values()):
            adjacency.setdefault(tuple(edge["depart"]), []).append(tuple(edge["arrivee"]))
    q = deque([(model.start, [])])
    visited = {model.start}
    route = None
    while q:
        pos, path = q.popleft()
        if pos[1] == min(y for x, y in visited) and pos[1] < model.start[1] - 2:
            route = path
            break
        for end in adjacency.get(pos, []):
            if end not in visited:
                visited.add(end)
                q.append((end, path + [end]))
    first = route[0] if route else None
    actual = {str(a): model.pas(model.depart, a)[0] for a in model.actions(model.depart)}
    retours = [x for x in records if x["action"] == 7]
    report = {
        "archives": len(paths),
        "transitions_uniques": len(records),
        "doublons": duplicates,
        "actions": dict(Counter("clic" if isinstance(x["action"], list) else str(x["action"]) for x in records)),
        "retours": {
            "n": len(retours),
            "niveaux": sorted({x["niveau"] for x in retours}),
            "position_changee_avant": sum(x.get("position_modifiee_avant_retour", False) for x in retours),
            "restauration_exacte": sum(x.get("restauration_exacte", False) for x in retours),
        },
        "enveloppe": {k: v for k, v in env.items() if k != "aretes"},
        "route_permissive": route,
        "premier_arret_manquant": first,
        "positions_premiere_action_native": actual,
        "premier_arret_realisable": first in actual.values() if first else False,
        "sdk": 0,
        "conclusion": "Aucun opérateur observé ne justifie les arrêts intermédiaires ; route permissive non soumise au SDK.",
    }
    (out / "rapport.json").write_text(json.dumps(report, indent=2, default=int))
    (out / "observations.json").write_text(json.dumps(records, indent=2, default=int))
    (out / "sources.json").write_text(json.dumps(sources, indent=2))
    (out / "enveloppe.json").write_text(json.dumps(env, indent=2, default=int))
    print(json.dumps(report, default=int))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
