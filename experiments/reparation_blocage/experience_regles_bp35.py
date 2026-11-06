"""Une trajectoire nouvelle ; choix et réfutation automatiques, aucune règle cible."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprendre_archive_bp35 import preparer
from boucle_navigation_visible import sauver
from boucle_objets_variables import LaboP1
from controleur_experimentation import Dossier
from hypotheses_navigation import HypothesesNavigation
from issues_observees import issue_sdk, scene_image
from proposeur_petites_regles import proposer

R = Path(__file__).resolve().parent


def cle(image, action):
    return hashlib.sha256(np.asarray(image, dtype=np.int16)[:-1].tobytes()).hexdigest() + json.dumps(
        action, default=int, separators=(",", ":")
    )


def choisir(evaluations, ids, image, connus):
    choices = []
    for e in evaluations:
        action = json.loads(json.dumps(e["actions"][0], default=int))
        if cle(image, action) in connus:
            continue
        predictions = {}
        for n in ids:
            if n in e["predictions"]:
                val = e["predictions"][n][0][0]
                predictions[n] = "defaite" if val == "mort" else val
        if len(predictions) != len(ids):
            continue
        outcomes = list(predictions.values())
        # D'abord séparer les clauses ; ensuite solliciter une condition encore non testée.
        score = (len(set(outcomes)), int(any(x != "continue" for x in outcomes)))
        choices.append((score, e, predictions))
    if not choices:
        return None
    _, e, predictions = max(choices, key=lambda c: c[0])
    return {
        "action": json.loads(json.dumps(e["actions"][0], default=int)),
        "predictions": predictions,
        "score": max(choices, key=lambda c: c[0])[0],
        "risque": "défaite possible ; expérience bornée, probabilités non calibrées",
    }


def choisir_bfws(image, local, learner, offre, connus):
    from experience_bfws import ExperienceLocale

    model = ExperienceLocale(image, local, {n: learner.candidats[n] for n in learner.actives(True)}, offre)
    interdits = {
        str(list(a) if isinstance(a, tuple) else a)
        for a in model.actions(model.depart)
        if cle(image, list(a) if isinstance(a, tuple) else a) in connus
    }
    r = model.chercher(interdits)
    action = r["plan"][0] if r["plan"] else None
    return {
        "action": list(action) if isinstance(action, tuple) else action,
        "predictions": r["etapes"][0]["predictions"] if r["plan"] else {},
        "recherche": r,
        "risque": "conditionnel au modèle local, défaite possible",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--bfws", action="store_true")
    args = parser.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    m, learner, old, oldrows = preparer(out, raffiner=True)
    files = sorted(R.glob("*.py"))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    sauver(out / "sources.json", hashes)
    sauver(out / "apprentissage_avant.json", learner.rapport())
    if not learner.actives(True):
        sauver(out / "bilan.json", {"statut": "aucune_explication", "sdk": 0})
        return
    connus = {cle(old["images"][i], row["action"]) for i, row in enumerate(oldrows)}
    # Les nouveaux essais antérieurs restent eux aussi exclus des interventions.
    previous = R / "runs/apprentissage_bp35_reel2/N2/partie"
    if previous.with_suffix(".json").exists():
        pj = json.loads(previous.with_suffix(".json").read_text())
        pz = np.load(previous.with_suffix(".npz"))
        connus.update(cle(pz["images"][i], row["action"]) for i, row in enumerate(pj["rows"]))
    if args.bfws:
        preview = HypothesesNavigation(m, clics=(True,))
        preview.observer(old["images"][0], oldrows[0]["action"], old["images"][1], old["film_1"])
        preflight = choisir_bfws(old["images"][1], preview, learner, [3, 4, 6], connus)
        sauver(out / "preflight_bfws.json", preflight)
        if preflight["action"] is None:
            sauver(out / "bilan.json", {"statut": "aucune_experience_separatrice_simulee", "sdk": 0})
            return
    access_source = R / "runs/bp35_navigation_visible_reprise1/N1/partie"
    az = np.load(access_source.with_suffix(".npz"))
    aj = json.loads(access_source.with_suffix(".json").read_text())
    lab = LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
    access = lab
    status = "budget"
    decisions = []
    try:
        for i, action in enumerate(aj["actions"]):
            image, film = lab.play(action, purpose="acces_N2_uniquement")
            if not np.array_equal(image, az["images"][i + 1]) or not np.array_equal(film, az[f"film_{i + 1}"]):
                raise ValueError("Accès divergent")
        if not lab.won:
            raise ValueError("N1 non gagné")
        lab = lab.next_level(out / "N2/partie")
        h = HypothesesNavigation(m, clics=(True,))
        before = lab.image.copy()
        image, film = lab.play(oldrows[0]["action"], purpose="restauration_prefixe_vivant")
        if not np.array_equal(image, old["images"][1]) or not np.array_equal(film, old["film_1"]):
            raise ValueError("Préfixe divergent")
        h.observer(before, oldrows[0]["action"], image, film)
        for k in range(8):
            ids = learner.actives(True)
            if not ids:
                status = "explications_refutees"
                break
            actions = [r["action"] for r in lab.rows]
            d = Dossier(
                lab.images,
                actions,
                [lab.films[f"film_{i + 1}"] for i in range(len(actions))],
                ["continue"] * len(actions),
                len(access.rows) + len(lab.rows),
                8 - k,
                tuple(int(getattr(a, "value", a)) for a in lab.actions_disponibles),
            )
            if args.bfws:
                decision = choisir_bfws(lab.image, h, learner, list(d.offre), connus)
                sauver(out / f"propositions_{k + 1}.json", decision)
                if decision["action"] is None:
                    decision = None
            else:
                p = proposer(d, {}, h, supplementaires=[learner.candidats[n] for n in ids])
                decision = choisir(p["experiences"], ids, lab.image, connus)
                sauver(out / f"propositions_{k + 1}.json", p)
            if decision is None:
                status = "pas_experience_nouvelle"
                break
            decision["hypotheses"] = ids
            sauver(out / f"prediction_avant_{k + 1}.json", decision)
            before = lab.image.copy()
            key = cle(before, decision["action"])
            assert key not in connus
            connus.add(key)
            image, film = lab.play(decision["action"], purpose="experience_clauses_nouvelle")
            issue = issue_sdk(lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 1)
            evidence = hashlib.sha256(film.tobytes() + key.encode()).hexdigest()
            result = learner.observer(
                [scene_image(g, m) for g in film], issue, evidence, prospectif=True, predictions=decision["predictions"]
            )
            decisions.append({"decision": decision, "observation": result})
            sauver(out / "apprentissage_apres.json", learner.rapport())
            if lab.finished:
                status = "victoire_reelle" if lab.won else "defaite_reelle"
                break
            h.observer(before, decision["action"], image, film, issue_observee=issue)
            if not h.actives():
                status = "dynamique_refutee"
                break
    except (ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
        status = "refus:" + repr(exc)
    finally:
        confirmed = [n for n in learner.actives(True) if any(s["prospectif"] for s in learner.supports[n])]
        bilan = {
            "statut": status,
            "coups_acces": len(access.rows),
            "coups_N2": len(lab.rows) if lab is not access else 0,
            "coups_totaux": len(access.rows) + (len(lab.rows) if lab is not access else 0),
            "initialisations": 1,
            "resets": 0,
            "predictions_confirmees_localement": confirmed,
            "expliquantes_restantes": learner.actives(True),
            "nouvelles_experiences": len(decisions),
            "aucune_injection": True,
            "sdk": True,
            "victoire_N2": lab is not access and lab.won,
            "sources_inchangees": hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        }
        sauver(out / "decisions.json", decisions)
        sauver(out / "bilan.json", bilan)
        print(json.dumps(bilan))


if __name__ == "__main__":
    main()
