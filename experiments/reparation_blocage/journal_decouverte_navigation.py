"""Lecture des observations, prédictions et films d'un essai ; zéro action SDK."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from evidence_films import Films


def exporter(run, niveau=1):
    partie = json.loads((run / f"N{niveau}/partie.json").read_text())
    journal = json.loads((run / "journal.json").read_text())
    decisions = {r["coup"]: r for r in journal}
    z = np.load(run / f"N{niveau}/partie.npz")
    dossier = run / "decouverte"
    dossier.mkdir(exist_ok=True)
    films = Films()
    cartes = []
    lignes = [
        "# Journal de découverte — observations, hypothèses, vérification",
        "",
        "Lecture rétrospective des traces. Les prédictions originales précèdent les actions ;",
        "les annotations de film ci-dessous sont postérieures et ne sont pas des entrées du décideur.",
        "Le signe de gravité, les cibles rares et la classe des blocs cliquables restent des hypothèses locales.",
        "La comparaison porte sur la position après estimation du défilement, pas sur tous les pixels.",
        "",
    ]
    for k, row in enumerate(partie["rows"], 1):
        before = z["images"][k - 1]
        film = z[f"film_{k}"]
        films.ajouter(before, film)
        d = decisions.get(k)
        info = films.analyser(k - 1)
        pages = []
        for i, data in enumerate(films.planches(k - 1)):
            name = f"coup_{k:02d}_film_{i:02d}.png"
            (dossier / name).write_bytes(data)
            pages.append(name)
        carte = {
            "coup": k,
            "action": row["action"],
            "observation_avant_sha256": hashlib.sha256(before.tobytes()).hexdigest(),
            "prediction_avant_action": d["decision"] if d else None,
            "statut_prediction": "archive de restauration" if d is None else "enregistree avant SDK",
            "film_apres": info,
            "pages": pages,
            "resultat_sdk": row,
            "position_conforme": d.get("position_conforme") if d else None,
            "attention": "corrélation temporelle, ne prouve pas une dynamique autonome",
        }
        cartes.append(carte)
        verdict = "restauration du préfixe vérifiée"
        if d:
            verdict = "position compatible après défilement" if d.get("position_conforme") else "position non évaluée"
        if "GAME_OVER" in row["state"]:
            verdict = "défaite réelle SDK ; aucune victoire de ce niveau"
        if row["levels_completed"] > niveau - 1:
            verdict = "niveau gagné, confirmation SDK ; jeu entier non confirmé"
        lignes += [f"## Coup {k} — {row['action']}", "", f"{verdict}. Film : {len(film)} images.", ""]
        if d and "gravite_hypothese" not in d["decision"]:
            lignes += [
                "Hypothèses avant : " + str(d["decision"]["hypotheses"]),
                "Vérification : " + str(d.get("verification", "transition terminale, aucune comparaison de position")),
                "",
            ]
        if d and "gravite_hypothese" in d["decision"]:
            p = d["decision"]
            lignes += [
                f"Hypothèse : gravité {p['gravite_hypothese']}, destination locale prévue au prochain coup {p['position_suivante_locale']}.",
                f"But encore hypothétique : {p['buts_hypothetiques']}. Plan local : {len(p['plan_local'])} coups ; seul le premier est exécuté.",
                "",
            ]
        lignes += [f"[Film complet, page {i + 1}]({name})" for i, name in enumerate(pages)] + [""]
    (dossier / "journal.md").write_text("\n".join(lignes))
    (dossier / "cartes.json").write_text(json.dumps(cartes, ensure_ascii=False, indent=2))
    return {"cartes": len(cartes), "frames": sum(c["film_apres"]["n_images"] for c in cartes), "sdk_supplementaire": 0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--niveau", type=int, default=1)
    args = ap.parse_args()
    print(json.dumps(exporter(args.run, args.niveau)))
