"""Une intervention nouvelle après déplacement, prévisions figées avant SDK."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import activation
from boucle_navigation_visible import sauver
from boucle_objets_variables import LaboP1
from hypotheses_annulation import comparer, variantes
from observation_censuree import issue_pour_revision
from perception_hierarchique import decomposer
from plan_phase import HorlogeArchive
from preflight_interventions_bp35 import charger

R = Path(__file__).parent
PREFIXES = ["bp35_navigation_visible_reprise1/N1", "remontee_bp35_reel1/N2", "route_phase_N3_reel2/N3"]


def charger_prefixe(name):
    p = R / "runs" / name / "partie"
    return np.load(p.with_suffix(".npz")), json.loads(p.with_suffix(".json").read_text())


def preparer():
    m, _, cs, *_ = charger()
    z, j = charger_prefixe(PREFIXES[-1])
    preds = variantes(z["images"], j["actions"], m)
    clock = HorlogeArchive(json.loads((R / "runs/horloges_N3_reel1/monde_temporel.json").read_text()))
    risks = {}
    for name, (im, dy) in preds.items():
        sc, _ = decomposer(im, m)
        actor = next(o for o in sc.sprites if "controle" in o.get("tags", ()))
        risks[name] = {
            "position": m.position(im),
            "camera": dy,
            "marge_front": clock.bord(len(j["actions"]) + 1) + dy - (actor["y"] + actor["pixels"].shape[0]),
            "clauses_actives": [n for n, c in cs.items() if activation(c["python"], [sc])],
        }
    return (
        m,
        preds,
        {
            "action": 7,
            "predictions": risks,
            "issues_distinctes": len({im[:-1].tobytes() for im, _ in preds.values()}),
            "admissible_modeles": all(not x["clauses_actives"] and x["marge_front"] > 0 for x in risks.values()),
            "limites": "états finaux partiels ; transition et autres effets inconnus ; garder une issue hors catalogue",
        },
    )


def main(out, executer):
    out.mkdir(exist_ok=False, parents=True)
    m, preds, pre = preparer()
    sauver(out / "preflight.json", pre)
    np.savez_compressed(out / "predictions.npz", **{k: v[0] for k, v in preds.items()})
    if not executer or not pre["admissible_modeles"]:
        print(json.dumps(pre))
        return
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")}
    sauver(out / "sources.json", sources)
    labs = []
    status = "initialisation"
    result = {}
    try:
        for level, name in enumerate(PREFIXES, 1):
            lab = (
                LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
                if level == 1
                else labs[-1].next_level(out / f"N{level}/partie")
            )
            labs.append(lab)
            z, j = charger_prefixe(name)
            for i, a in enumerate(j["actions"]):
                im, film = lab.play(a, purpose="acces_experience_annulation")
                if not np.array_equal(im, z["images"][i + 1]) or not np.array_equal(film, z[f"film_{i + 1}"]):
                    raise ValueError("Accès divergent")
            if level < 3 and not lab.won:
                raise ValueError("Niveau accès non gagné")
        sauver(out / "offre_avant.json", lab.actions_disponibles)
        if 7 not in lab.actions_disponibles:
            raise ValueError("Action7 non offerte")
        before = lab.image.copy()
        im, film = lab.play(7, purpose="departager_annulation_apres_deplacement")
        result = comparer(im, preds)
        result["validite"] = issue_pour_revision(im, m, lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 2)
        result["frames"] = len(film)
        result["pixels_hud_changes"] = int(np.sum(before[-1] != im[-1]))
        result["etat_sdk"] = lab.rows[-1]["state"]
        result["niveaux"] = lab.rows[-1]["levels_completed"]
        result["victoire_N3"] = lab.won
        try:
            result["position_apres"] = m.position(im)
        except ValueError:
            result["position_apres"] = None
        status = "experience_terminee"
    except (ValueError, RuntimeError, IndexError, KeyError, TypeError) as exc:
        status = "arret:" + repr(exc)
    finally:
        sauver(out / "comparaison.json", result)
        bilan = {
            "statut": status,
            "coups_par_niveau": [len(l.rows) for l in labs],
            "coups_total": sum(len(l.rows) for l in labs),
            "initialisations": 1,
            "resets": 0,
            "sources_inchangees": sources == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")},
        }
        sauver(out / "bilan.json", bilan)
        print(json.dumps(bilan))
        print(json.dumps(result))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--executer", action="store_true")
    args = ap.parse_args()
    main(args.sortie, args.executer)
