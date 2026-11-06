"""Diagnostic hors ligne des seuls cas terminés, sans accès au générateur/oracle."""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from classification_prefixe import classifier


def main(source, sortie):
    resume = json.loads((source / "resume.json").read_text())
    termines = [r for r in resume["resultats"] if r["statut_runner"] == "termine"]
    sortie.mkdir(parents=True, exist_ok=False)
    results = []
    for r in termines:
        # Le nom sert uniquement à localiser l'archive et étiqueter le rapport externe.
        dossier = source / r["jeu"]
        p = dossier / "N1/partie"
        if not p.with_suffix(".npz").exists():
            continue
        rows = json.loads(p.with_suffix(".json").read_text())["rows"]
        n = min(4, len(rows))
        with np.load(p.with_suffix(".npz")) as z:
            images = z["images"][: n + 1].copy()
            films = [z[f"film_{i + 1}"].copy() for i in range(n)]
        actions = [row["action"] for row in rows[:n]]
        description = classifier(images, actions, films)
        (sortie / (r["jeu"] + ".json")).write_text(json.dumps(description, ensure_ascii=False, indent=2))
        journal = json.loads((dossier / "journal.json").read_text()) if (dossier / "journal.json").exists() else []
        fails = Counter(x.get("raison") for x in journal if x["type"] == "capacite_non_applicable")
        admissions = [x for x in journal if x["type"] == "admission"]
        results.append(
            {
                "cas_archive": r["jeu"],
                "prefixe_actions": n,
                "translation": description["translation"]["statut"],
                "transformation": description["transformation_motif"]["statut"],
                "capacites": description["capacites_a_essayer"],
                "canaux": description["canaux_observes"],
                "films_inertes_sans_masque": sum(x["inerte"] for x in description["films"]),
                "admissions_testees": len(admissions),
                "admissions_compatibles": sum(x["controle"].get("rejeu") is True for x in admissions),
                "refus_capacites": dict(fails),
            }
        )
    synthese = {
        "complet_104": resume["complet"],
        "cas_termines_snapshot": len(termines),
        "cas_analyses": len(results),
        "aucune_source_oracle": True,
        "aucune_action_SDK": True,
        "statuts_translation": dict(Counter(x["translation"] for x in results)),
        "capacites_suggerees": dict(Counter(c for x in results for c in x["capacites"])),
        "sans_admission": sum(x["admissions_compatibles"] == 0 for x in results),
        "cas": results,
    }
    (sortie / "synthese.json").write_text(json.dumps(synthese, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in synthese.items() if k != "cas"}, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    a = ap.parse_args()
    main(a.source, a.sortie)
