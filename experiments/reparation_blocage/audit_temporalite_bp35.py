"""Audit nouveau des horloges sur archives uniquement, sans rejouer les expériences."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import activation
from boucle_navigation_visible import decalage
from espace_experiences import partitions
from experience_regles_bp35 import cle
from issues_observees import issue_sdk
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger
from temporalite_contacts import delais_compatibles, resumer

R = Path(__file__).resolve().parent


def analyser(out):
    out.mkdir(parents=True, exist_ok=False)
    m, _, cs, _, _, _ = charger()
    cachepath = R / "runs/hierarchie_bp35_2/rapport.json"
    cache = json.loads(cachepath.read_text())
    assert cache["hypotheses"] == cs
    episodes, doublons, vus, empreintes = [], [], {}, {}
    empreintes[str(cachepath)] = hashlib.sha256(cachepath.read_bytes()).hexdigest()
    for name in ("bp35_N2_hypotheses_neuronal_reprise1", "apprentissage_bp35_reel2", "frontiere_bp35_reel2"):
        path = R / "runs" / name / "N2/partie"
        for suffix in (".npz", ".json"):
            p = path.with_suffix(suffix)
            empreintes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        z = np.load(path.with_suffix(".npz"))
        rows = json.loads(path.with_suffix(".json").read_text())["rows"]
        for i, row in enumerate(rows):
            before, film = z["images"][i], z[f"film_{i + 1}"]
            key = hashlib.sha256((cle(before, row["action"]) + hashlib.sha256(film.tobytes()).hexdigest()).encode()).hexdigest()
            ident = f"{name}/{i + 1}"
            if key in vus:
                doublons.append({"episode": ident, "identique_a": vus[key]})
                continue
            vus[key] = ident
            if name == "bp35_N2_hypotheses_neuronal_reprise1":
                frames = [f for f in cache["films"] if f["coup"] == i + 1]
                assert len(frames) == len(film)
                provenance = "activations du précédent audit réutilisées"
            else:
                frames = []
                _, _, origin = m.lire(before)
                for rank, g in enumerate(film):
                    dy, err = decalage(before, g, m.palette)
                    sc, _ = decomposer(g, m, (origin[0], origin[1] + dy))
                    actors = [a for a in sc.sprites if "controle" in a.get("tags", ())]
                    frames.append(
                        {
                            "frame": rank,
                            "controle_visible": len(actors) == 1,
                            "pixels_inexpliques": int(np.sum(sc.image()[:-1] != g[:-1])),
                            "camera_dy": dy,
                            "camera_erreur": err,
                            "regles": {n: {"active": activation(c["python"], [sc]) is not None} for n, c in cs.items()},
                        }
                    )
                provenance = "projection sur film archivé, nouveau diagnostic temporel"
            episodes.append(
                {
                    "id": ident,
                    "empreinte": key,
                    "issue": issue_sdk(row["state"], row["levels_completed"], 1),
                    "action": row["action"],
                    "provenance": provenance,
                    "frames": frames,
                    **resumer(frames, cs),
                }
            )
    matrice = [[f["regles"][n]["active"] for n in cs] for e in episodes for f in e["frames"] if f["controle_visible"]]
    part = partitions(matrice)
    fatal = [e for e in episodes if e["issue"] == "defaite" and e["pertes_reconnaissance"]]
    delais = {
        n: delais_compatibles([e["premiere_activation"][n] for e in fatal], [(e["pertes_reconnaissance"][0],) * 2 for e in fatal])
        for n in cs
    }
    rapport = {
        "sdk": 0,
        "nouveaux_coups": 0,
        "initialisations": 0,
        "hypotheses": cs,
        "episodes": episodes,
        "doublons_exclus": doublons,
        "partitions_temporelles": part,
        "classes_temporelles": [[list(cs)[i] for i in groupe] for groupe in part["classes_indiscernables"]],
        "delais_vers_perte_reconnaissance": delais,
        "regles_refutees": [],
        "limite": "Pas de métadonnée SDK par frame, pas de délai animation calibré ; différences internes ne sont pas des réfutations.",
        "empreintes_traces": empreintes,
        "empreintes_code": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                R / "temporalite_contacts.py",
                R / "perception_hierarchique.py",
                R / "apprentissage_regles.py",
            ]
        },
    }
    (out / "rapport.json").write_text(json.dumps(rapport, indent=2, default=int))
    print(
        json.dumps(
            {
                "episodes_uniques": len(episodes),
                "doublons": len(doublons),
                "frames": sum(len(e["frames"]) for e in episodes),
                "classes": rapport["classes_temporelles"],
                "delais": delais,
                "erreurs_pixels": sum(f["pixels_inexpliques"] for e in episodes for f in e["frames"]),
            }
        )
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    analyser(ap.parse_args().sortie)
