"""Avancer par consensus des hypothèses, observation et replanification."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import Apprentissage
from boucle_navigation_visible import decalage, sauver
from boucle_objets_variables import LaboP1
from experience_regles_bp35 import cle
from issues_observees import issue_sdk
from perception_hierarchique import decomposer
from plan_remontee import decision
from preflight_interventions_bp35 import charger

R = Path(__file__).resolve().parent


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
    prefix = R / "runs/branche_bp35_reel1/N2/partie"
    pz = np.load(prefix.with_suffix(".npz"))
    pj = json.loads(prefix.with_suffix(".json").read_text())
    known.update(cle(pz["images"][i], action) for i, action in enumerate(pj["actions"]))
    # Rejoindre directement la fin de l'aller validé : ne pas rejouer le retour puis l'aller.
    pj["actions"] = pj["actions"][:35]
    other = R / "runs/consensus_bp35_reel1/N2/partie"
    oz = np.load(other.with_suffix(".npz"))
    oj = json.loads(other.with_suffix(".json").read_text())
    known.update(cle(oz["images"][i], action) for i, action in enumerate(oj["actions"]))
    pre = decision(pz["images"][35], h, cs, known, 32)
    sauver(out / "preflight.json", pre)
    if not args.executer or not pre["plan"]:
        print(json.dumps(pre, default=int))
        return
    a = Apprentissage(
        [{"id": n, **c} for n, c in cs.items()],
        out / "memoire.json",
        {"famille": "navigation_gravite_clic", "portee": "bp35N2", "transfert_autorise": False},
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
        for i, action in enumerate(pj["actions"]):
            im, film = lab.play(action, purpose="acces_frontiere_connue")
            if not np.array_equal(im, pz["images"][i + 1]) or not np.array_equal(film, pz[f"film_{i + 1}"]):
                raise ValueError("Préfixe N2 divergent")
        for k in range(32):
            current = {n: cs[n] for n in a.actives()}
            d = decision(lab.image, h, current, known, 32 - k, lab.actions_disponibles)
            d["offre_reelle"] = lab.actions_disponibles
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
            "nouveaux_coups": max(0, len(lab.rows) - len(pj["actions"])) if lab is not access else 0,
            "coups_acces_N2": min(len(lab.rows), len(pj["actions"])) if lab is not access else 0,
        }
        sauver(out / "bilan.json", bilan)
        sauver(out / "historique.json", history)
        sauver(out / "dynamique.json", h.journal)
        print(json.dumps(bilan))


if __name__ == "__main__":
    main()
