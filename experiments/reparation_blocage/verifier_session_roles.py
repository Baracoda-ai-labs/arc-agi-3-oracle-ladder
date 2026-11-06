"""Audit hors jeu des preuves, compteurs et prédictions de la session sauvegardée."""

import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    root = Path(__file__).resolve().parent / "ka59_roles"
    journal = json.loads((root / "session/journal.json").read_text())
    partie = json.loads((root / "session/N1/partie.json").read_text())
    bilan = json.loads((root / "session/bilan.json").read_text())
    z = np.load(root / "session/N1/partie.npz")
    controles = []
    for e in journal:
        if "experience" not in e:
            continue
        # Chemins indépendants du poste où l'audit est relu.
        relatif = e["experience"].split("/ka59_roles/", 1)[1]
        raw = (root / relatif).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == e["sha256"]
        controles.append({"experience": relatif, "sha256_verifie": True, "coups": [r["coup"] for r in e["resultats"]]})
    assert len(partie["rows"]) == bilan["coups_reels"] == 39
    assert len(z["images"]) == 40
    assert partie["rows"][-1]["levels_completed"] == 1 and bilan["niveaux_gagnes"] == 1
    e = json.loads((root / "apres_film_surface/experience.json").read_text())
    pred = np.array(e["predictions"][-1][0]["image"])
    obs = z["film_39"][0].copy()
    for y, x in e["hud"]:
        pred[y, x] = obs[y, x] = 0
    assert np.array_equal(pred, obs)
    suivante = z["film_39"][-1].copy()
    for y, x in e["hud"]:
        suivante[y, x] = 0
    ecart_suivante = int(np.count_nonzero(pred != suivante))
    result = {
        "empreintes_experiences": controles,
        "coups_reels": 39,
        "dont_restauration": 8,
        "coups_apres_restauration": 31,
        "initialisations": 1,
        "resets_supplementaires": 0,
        "niveaux_gagnes_sdk": 1,
        "jeu_gagne": False,
        "images_finales": 40,
        "frames_retournees": sum(len(z[f"film_{k}"]) for k in range(1, 40)),
        "terminal_pred_frames_0_ecart": 0,
        "ecart_frame_suivante": ecart_suivante,
        "note": "La dernière frame est le niveau suivant, aucune action sur celui-ci.",
    }
    (root / "audit_final.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
