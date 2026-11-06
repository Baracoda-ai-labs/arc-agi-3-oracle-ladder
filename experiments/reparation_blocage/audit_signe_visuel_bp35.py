"""Détecteur sans labels ; comparaison aux issues uniquement après extraction."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from preflight_interventions_bp35 import charger
from signe_visuel import apprendre, detecter

R = Path(__file__).resolve().parent


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    m, *_ = charger()
    profil = apprendre(m)
    archive = R / "runs/temporalite_bp35_1/rapport.json"
    old = json.loads(archive.read_text())
    results = []
    for e in old["episodes"]:
        name, step = e["id"].split("/")
        z = np.load(R / "runs" / name / "N2/partie.npz")
        film = z[f"film_{step}"]
        local = apprendre(m, [z["images"][int(step) - 1]])
        detection = detecter(film, local)
        results.append(
            {
                "episode": e["id"],
                "detection": detection,
                "profil_avant_action": local,
                "sensibilite_persistance": {str(k): detecter(film, local, k)["debut"] for k in (1, 2, 3)},
                "hud_modifie_frames": [i for i in range(1, len(film)) if not np.array_equal(film[i, -1], film[i - 1, -1])],
                "activation_regles": e["premiere_activation"],
                "issue_pour_audit_uniquement": e["issue"],
            }
        )
    rapport = {
        "profil_appris_reference": profil,
        "episodes": results,
        "sdk": 0,
        "regles_refutees": [],
        "limite": "Signal visible sans statut, mais délai collision-animation non calibré ; occlusion/changement apparence encore possibles.",
        "sources": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [archive, Path(__file__), R / "signe_visuel.py"]},
    }
    (out / "rapport.json").write_text(json.dumps(rapport, indent=2))
    print(json.dumps({"profil": profil, "signaux": [(e["episode"], e["detection"]["debut"]) for e in results]}))
    # Figure de diagnostic : palette discrète de visualisation, pas couleurs originales.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    z = np.load(R / "runs/bp35_N2_hypotheses_neuronal_reprise1/N2/partie.npz")
    fig, axes = plt.subplots(1, 6, figsize=(12, 3))
    for ax, i in zip(axes, range(12, 18), strict=True):
        ax.imshow(z["film_2"][i], vmin=0, vmax=15, cmap="tab20", interpolation="nearest")
        ax.set_title(f"Image {i}")
        ax.axis("off")
    fig.suptitle("Diagnostic visuel — couleurs de visualisation, aucun lissage")
    fig.tight_layout()
    fig.savefig(out / "sequence.png")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    main(ap.parse_args().sortie)
