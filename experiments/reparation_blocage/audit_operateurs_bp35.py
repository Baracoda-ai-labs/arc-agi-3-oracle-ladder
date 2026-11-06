import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from boucle_navigation_visible import decalage
from issues_observees import scene_image
from operateurs_memoire import verifier_retours
from preflight_interventions_bp35 import charger

from chrysalide.arc3.logique.induction import trouver_annulation

R = Path(__file__).resolve().parent


def empreinte(g):
    return hashlib.sha256(g[:-1].tobytes()).hexdigest()


def actor(g, m):
    found = [o for o in scene_image(g, m).sprites if "controle" in o.get("tags", ())]
    return found[0] if len(found) == 1 else None


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    m, h, *_ = charger()
    nom = h.actives()[0]
    paths = [
        "publics_ref_g0/bp35/N1",
        "bp35_navigation_visible_reprise1/N1",
        "bp35_sans_but_fige1/N1",
        "roles_autonomes_bp35_fige1/N1",
        "bp35_N2_hypotheses_neuronal_reprise1/N2",
        "apprentissage_bp35_reel2/N2",
        "frontiere_bp35_reel2/N2",
    ]
    vus = set()
    records = []
    sources = {}
    retours = []
    doublons = 0
    for name in paths:
        p = R / "runs" / name / "partie"
        j = json.loads(p.with_suffix(".json").read_text())
        z = np.load(p.with_suffix(".npz"))
        for ext in (".json", ".npz"):
            sources[str(p.with_suffix(ext))] = hashlib.sha256(p.with_suffix(ext).read_bytes()).hexdigest()
        actions = [tuple(a) if isinstance(a, list) else a for a in j["actions"]]
        states = [empreinte(g) for g in z["images"][: len(actions) + 1]]
        trace = SimpleNamespace(etats=states, actions=actions)
        undo = trouver_annulation([(trace, list(range(len(actions))))])
        if undo is not None:
            tests = verifier_retours(states, actions, undo)
            retours.append(
                {
                    "source": name,
                    "code": undo,
                    "tests": tests,
                    "sortes_actions_defaites": sorted(
                        {
                            str(
                                actions[t["index"] - 1][0]
                                if isinstance(actions[t["index"] - 1], tuple)
                                else actions[t["index"] - 1]
                            )
                            for t in tests
                        }
                    ),
                    "restauration_image_entiere": sum(
                        np.array_equal(z["images"][t["index"] + 1], z["images"][t["index"] - 1]) for t in tests
                    ),
                    "hud_different": sum(
                        not np.array_equal(z["images"][t["index"] + 1][-1], z["images"][t["index"] - 1][-1]) for t in tests
                    ),
                }
            )
        for i, a in enumerate(actions):
            before, after = z["images"][i : i + 2]
            film = z[f"film_{i + 1}"] if f"film_{i + 1}" in z.files else None
            key = (
                j["level"],
                states[i],
                str(a),
                states[i + 1],
                hashlib.sha256(film.tobytes()).hexdigest() if film is not None else "film_absent",
            )
            if key in vus:
                doublons += 1
                continue
            vus.add(key)
            record = {
                "source": name,
                "coup": i + 1,
                "action": a,
                "frames": len(film) if film is not None else None,
                "pixels_scene_changes": int(np.sum(before[:-1] != after[:-1])),
                "hud_change": not np.array_equal(before[-1], after[-1]),
                "modele_action_couverte": isinstance(a, tuple) or a in (3, 4),
            }
            try:
                ba, aa = actor(before, m), actor(after, m)
                if ba is not None and aa is not None:
                    bpatch, apatch = ba["pixels"], aa["pixels"]
                    record["reflet_observe"] = not np.array_equal(bpatch, apatch) and np.array_equal(bpatch[:, ::-1], apatch)
                if record["modele_action_couverte"]:
                    pred = h.predire(before, list(a) if isinstance(a, tuple) else a, nom)
                    dy, err = decalage(before, after, m.palette)
                    actual = m.position(after)
                    px, py = pred["position"]
                    ox, oy = pred["origine"]
                    expected = (ox + px * m.pas + m.pas // 2, oy + py * m.pas + m.pas // 2 + dy)
                    record.update(camera_erreur=err, position_conforme=actual == expected, position=actual)
                    record["position_inchangee"] = m.position(before) == actual
                    record["comparison_eligible"] = err <= 0.15
            except (ValueError, IndexError, StopIteration) as exc:
                record["non_comparable"] = str(exc)
            records.append(record)
    summary = {
        "transitions_uniques": len(records),
        "doublons_exclus": doublons,
        "actions": dict(Counter("clic" if isinstance(e["action"], tuple) else str(e["action"]) for e in records)),
        "reflets": sum(e.get("reflet_observe", False) for e in records),
        "positions_comparables": sum(e.get("comparison_eligible", False) for e in records),
        "positions_divergentes": [
            {"source": e["source"], "coup": e["coup"]}
            for e in records
            if e.get("comparison_eligible") and not e["position_conforme"]
        ],
        "retours": retours,
        "sdk": 0,
        "regles_contact_refutees": [],
        "limite": "Comparaison de positions après recalage caméra, pas vérification complète des effets.",
    }
    rapport = {"resume": summary, "transitions": records, "sources": sources}
    (out / "rapport.json").write_text(json.dumps(rapport, indent=2, default=int))
    print(json.dumps({k: v for k, v in summary.items() if k != "retours"}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
