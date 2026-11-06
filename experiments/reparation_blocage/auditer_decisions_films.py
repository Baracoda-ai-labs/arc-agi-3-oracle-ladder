"""Retour arrière sur les décisions archivées, sans inverser la physique ni agir."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from evidence_films import Films


def auditer(run):
    z = np.load(run / "N1/partie.npz")
    partie = json.loads((run / "N1/partie.json").read_text())
    journal = json.loads((run / "journal.json").read_text())
    par_coup = {}
    for decision in journal:
        if "cycle" not in decision:
            continue
        for r in decision["resultats"]:
            par_coup[r["coup"]] = (decision, r)
    films = Films()
    for k in range(1, len(partie["rows"]) + 1):
        films.ajouter(z["images"][k - 1], z[f"film_{k}"])
    cartes = []
    for k in sorted(par_coup, reverse=True):
        decision, resultat = par_coup[k]
        infos = films.analyser(k - 1)
        film = z[f"film_{k}"]
        changements = [int(np.count_nonzero(a != b)) for a, b in zip([z["images"][k - 1], *film[:-1]], film, strict=True)]
        questions = ["Quel objet ou attribut répond à cette commande, et lequel reste inchangé ?"]
        if len(film) > 1:
            questions += [
                "Les phases observées sont-elles une interpolation de la commande, une propagation, ou une évolution autonome ?",
                "Quelle commande distincte, dans un contexte comparable, départagerait ces trois explications ?",
            ]
        if any(not r["conforme"] for r in resultat["comparaisons"]):
            questions.append("Quelle hypothèse locale explique le changement que le modèle ne prévoyait pas ?")
        if k == len(partie["rows"]) and "GAME_OVER" in partie["rows"][k - 1]["state"]:
            questions.append("Un signal observable de réserve ou de danger précédait-il cet échec ?")
        prefixe = run / f"decision_{decision['cycle']:02d}/prefixe.npz"
        avant = np.load(prefixe)["images"]
        assert len(avant) == decision["avant"] + 1
        assert np.array_equal(avant, z["images"][: len(avant)])
        cartes.append(
            {
                "coup": k,
                "action": partie["rows"][k - 1]["action"],
                "entree_causale": {
                    "prefixe": str(prefixe.relative_to(run)),
                    "jusqua_coup": decision["avant"],
                    "sha256": hashlib.sha256(prefixe.read_bytes()).hexdigest(),
                },
                "annotation_retrospective_ne_pas_injecter_dans_entree": {
                    "pixels_changes_par_phase": changements,
                    "film": infos,
                    "questions_candidates": questions,
                    "attribution_causale": "indeterminee",
                    "hypotheses_concurrentes": ["reponse_commande", "animation_commande", "dynamique_autonome"],
                },
                "portee": "cas de développement ; ni meilleure action démontrée, ni preuve de causalité",
            }
        )
    return {
        "ordre": "échec vers les décisions antérieures",
        "nombre_cartes": len(cartes),
        "sdk_supplementaire": 0,
        "hypothese_optimale": False,
        "cartes": cartes,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    args = ap.parse_args()
    rapport = auditer(args.run)
    args.sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=2))
    print(json.dumps({"cartes": rapport["nombre_cartes"], "sdk": 0, "ordre_coups": [c["coup"] for c in rapport["cartes"]]}))


if __name__ == "__main__":
    main()
