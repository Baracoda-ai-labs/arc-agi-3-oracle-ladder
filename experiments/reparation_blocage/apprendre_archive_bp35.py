"""Assimilation nouvelle d'une observation déjà payée, aucune nouvelle partie."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import Apprentissage
from issues_observees import issue_sdk, scene_image
from navigation_gravite_visible import NavigationVisible

R = Path(__file__).resolve().parent


def preparer(out, raffiner=False):
    prefix = R / "runs/controleur_trois_archives_fige1/bp35"
    ref = np.load(prefix / "reference.npz")
    meta = json.loads((prefix / "reference.json").read_text())
    m = NavigationVisible(ref["images"], meta["actions"])
    m.cassables = set(meta["cassables"])
    m.perception_connexe = True
    frozen = R / "runs/petites_regles_trois_archives_fige1/bp35/decision.json"
    candidats = json.loads(frozen.read_text())["petites_regles"]["candidats"]
    src = R / "runs/bp35_N2_hypotheses_neuronal_reprise1/N2/partie"
    data = np.load(src.with_suffix(".npz"))
    rows = json.loads(src.with_suffix(".json").read_text())["rows"]
    if raffiner:
        from raffinement_distance import distances, etendre

        marges = distances([scene_image(g, m) for g in data["film_2"]])
        candidats += etendre(candidats, marges)
        (out / "raffinement.json").write_text(json.dumps({"distances_mesurees": marges, "candidats": len(candidats)}))
    a = Apprentissage(
        candidats,
        out / "memoire.json",
        {
            "famille": "navigation_gravite_clic",
            "portee_validee": "episodes_bp35_N2_uniquement",
            "transfert_autorise": False,
            "perception": "motif_connexe_et_grille_appris_N1",
        },
    )
    for i, row in enumerate(rows):
        film = data[f"film_{i + 1}"]
        issue = issue_sdk(row["state"], row["levels_completed"], 1)
        preuve = hashlib.sha256(film.tobytes() + str(row["action"]).encode()).hexdigest()
        a.observer([scene_image(g, m) for g in film], issue, preuve)
    sources = [frozen, prefix / "reference.json", prefix / "reference.npz", src.with_suffix(".json"), src.with_suffix(".npz")]
    (out / "sources_entrees.json").write_text(
        json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2)
    )
    return m, a, data, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--raffiner", action="store_true")
    args = parser.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    _m, a, _data, _rows = preparer(out, args.raffiner)
    (out / "rapport.json").write_text(json.dumps(a.rapport(), indent=2))
    print(
        json.dumps(
            {
                "actives": len(a.actives()),
                "expliquantes": [{k: a.candidats[n][k] for k in ("id", "cible", "relation", "effet")} for n in a.actives(True)],
                "sdk": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
