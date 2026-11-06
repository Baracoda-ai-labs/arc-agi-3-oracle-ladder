"""Acquérir une vue nouvelle avant de chercher un départage impossible localement."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import Apprentissage
from boucle_navigation_visible import decalage, sauver
from boucle_objets_variables import LaboP1
from experience_bfws import ExperienceLocale, techniques
from experience_regles_bp35 import cle
from interventions_elargies import InterventionsElargies
from issues_observees import issue_sdk
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger

R = Path(__file__).resolve().parent


def decision(image, h, cs, known, remaining):
    if len(cs) < 2:
        return {"plan": None, "raison": "moins_de_deux_regles"}
    factory = lambda im, m: decomposer(im, m)[0]
    wide = InterventionsElargies(image, h, cs, [3, 4, 6], horizon=min(8, remaining), scene_factory=factory)
    blocked = {
        str(list(a) if isinstance(a, tuple) else a)
        for a in wide.actions(wide.depart)
        if cle(image, list(a) if isinstance(a, tuple) else a) in known
    }
    split = wide.chercher_minimal(blocked, max_noeuds=3000)
    if split["plan"]:
        return {**split, "raison": "departage"}
    model = ExperienceLocale(image, h, cs, [3, 4, 6], horizon=min(8, remaining), scene_factory=factory)
    edge = min(y for x, y in model.free | model.blocks) if model.g < 0 else max(y for x, y in model.free | model.blocks)

    def goal(s):
        return s[0][1] == edge and all(v == "continue" for v in s[2]) and s[3] > 0

    def actions(s):
        return [
            a for a in model.actions(s) if s != model.depart or cle(image, list(a) if isinstance(a, tuple) else a) not in known
        ]

    plan = techniques().bfs(model.depart, model.pas, actions, goal, max_noeuds=3000)
    cur = model.depart
    steps = []
    if plan:
        for a in plan:
            cur = model.pas(cur, a)
            steps.append({"position": cur[0], "predictions": dict(zip(cs, cur[2], strict=True))})
    return {
        "plan": plan,
        "etapes": steps,
        "raison": "acquisition_frontiere_non_separatrice",
        "transitions": len(model.cache),
        "risque": "modèle partiel ; inconnus au-delà de la vue",
    }


def scenes_film(before, film, modele):
    _, _, origin = modele.lire(before)
    return [decomposer(g, modele, (origin[0], origin[1] + decalage(before, g, modele.palette)[0]))[0] for g in film]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--executer", action="store_true")
    args = ap.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    m, h, cs, old, rows, known = charger()
    pre = decision(old["images"][1], h, cs, known, 8)
    sauver(out / "preflight.json", pre)
    if not args.executer or not pre["plan"]:
        print(json.dumps(pre, default=int))
        return
    a = Apprentissage(
        [{"id": n, **c} for n, c in cs.items()], out / "memoire.json", {"famille": "navigation_gravite_clic", "portee": "bp35N2", "transfert_autorise": False}
    )
    # La mémoire existante fournit les clauses ; films historiques restent sources.
    for i, row in enumerate(rows):
        a.observer(
            scenes_film(old["images"][i], old[f"film_{i + 1}"], m),
            issue_sdk(row["state"], row["levels_completed"], 1),
            f"archive_{i}",
        )
    source = R / "runs/bp35_navigation_visible_reprise1/N1/partie"
    z = np.load(source.with_suffix(".npz"))
    j = json.loads(source.with_suffix(".json").read_text())
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")}
    sauver(out / "sources.json", hashes)
    lab = LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
    access = lab
    status = "budget"
    history = []
    try:
        for i, action in enumerate(j["actions"]):
            im, film = lab.play(action, purpose="acces_N2_seulement")
            if not np.array_equal(im, z["images"][i + 1]) or not np.array_equal(film, z[f"film_{i + 1}"]):
                raise ValueError("Accès divergent")
        if not lab.won:
            raise ValueError("Accès non gagné")
        lab = lab.next_level(out / "N2/partie")
        im, film = lab.play(rows[0]["action"], purpose="restauration_prefixe")
        if not np.array_equal(im, old["images"][1]) or not np.array_equal(film, old["film_1"]):
            raise ValueError("Préfixe divergent")
        for k in range(8):
            current = {n: cs[n] for n in a.actives()}
            d = decision(lab.image, h, current, known, 8 - k)
            sauver(out / f"decision_avant_{k + 1}.json", d)
            if not d["plan"]:
                status = d["raison"]
                break
            action = d["plan"][0]
            action = json.loads(json.dumps(action, default=int))
            before = lab.image.copy()
            key = cle(before, action)
            if key in known:
                raise ValueError("Expérience déjà enregistrée")
            code = 6 if isinstance(action, list) else action
            if code not in lab.actions_disponibles:
                raise ValueError("Action indisponible")
            known.add(key)
            im, film = lab.play(action, purpose=d["raison"])
            issue = issue_sdk(lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 1)
            # Le rôle contrôle détermine la phase de grille avant l'action ; caméra du film recale ensuite.
            scenes = scenes_film(before, film, m)
            obs = a.observer(
                scenes, issue, hashlib.sha256(film.tobytes() + key.encode()).hexdigest(), True, d["etapes"][0]["predictions"]
            )
            history.append({"action": action, "raison": d["raison"], "observation": obs})
            sauver(out / "apprentissage.json", a.rapport())
            if lab.finished:
                status = "victoire_N2" if lab.won else "defaite"
                break
            h.observer(before, action, im, film, issue_observee=issue)
            if not h.actives():
                status = "dynamique_refutee"
                break
    except (ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        status = "refus:" + repr(exc)
    finally:
        bilan = {
            "statut": status,
            "coups_acces": len(access.rows),
            "coups_N2": len(lab.rows) if lab is not access else 0,
            "initialisations": 1,
            "resets": 0,
            "actives": a.actives(),
            "hypotheses_initiales": list(cs),
            "sources_inchangees": hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")},
            "experiences_separatrices_jouees": sum(e["raison"] == "departage" for e in history),
        }
        sauver(out / "bilan.json", bilan)
        sauver(out / "historique.json", history)
        print(json.dumps(bilan))


if __name__ == "__main__":
    main()
