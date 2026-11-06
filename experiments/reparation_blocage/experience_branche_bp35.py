import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import Apprentissage
from boucle_navigation_visible import sauver
from boucle_objets_variables import LaboP1
from branche_retour import chercher, retour
from experience_bfws import ExperienceLocale
from experience_frontiere_bp35 import scenes_film
from experience_regles_bp35 import cle
from issues_observees import issue_sdk
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger

R = Path(__file__).resolve().parent


def modele(image, h, cs, offre):
    return ExperienceLocale(image, h, cs, offre, horizon=24, scene_factory=lambda im, m: decomposer(im, m)[0])


def main(out, executer):
    out.mkdir(parents=True, exist_ok=False)
    m, h, cs, _, _, known = charger()
    src = R / "runs/consensus_bp35_reel1/N2/partie"
    z = np.load(src.with_suffix(".npz"))
    j = json.loads(src.with_suffix(".json").read_text())
    known.update(cle(z["images"][i], a) for i, a in enumerate(j["actions"]))
    choisi = None
    audits = []
    for i in range(len(j["actions"]) - 1, 7, -1):
        b = modele(z["images"][i], h, cs, [3, 4, 6])
        bans = {
            str(list(a) if isinstance(a, tuple) else a)
            for a in b.actions(b.depart)
            if cle(z["images"][i], list(a) if isinstance(a, tuple) else a) in known
        }
        d = chercher(b, bans)
        audits.append({"apres_coups_N2": i, **d})
        if d["plan"]:
            choisi = (i, d)
            break
    sauver(out / "preflight.json", audits)
    if not executer or choisi is None:
        print(json.dumps(audits, default=int))
        return
    i, d = choisi
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")}
    sauver(out / "sources.json", hashes)
    learner = Apprentissage(
        [{"id": n, **c} for n, c in cs.items()], out / "memoire.json", {"portee": "bp35N2", "transfert_autorise": False}
    )
    lab = LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
    access = lab
    hist = []
    status = "budget"
    newcount = 0
    try:
        p = R / "runs/bp35_navigation_visible_reprise1/N1/partie"
        nz = np.load(p.with_suffix(".npz"))
        nj = json.loads(p.with_suffix(".json").read_text())
        for k, a in enumerate(nj["actions"]):
            im, film = lab.play(a, purpose="acces_N2")
            if not np.array_equal(im, nz["images"][k + 1]) or not np.array_equal(film, nz[f"film_{k + 1}"]):
                raise ValueError("Accès N1 divergent")
        if not lab.won:
            raise ValueError("N1 non gagné")
        lab = lab.next_level(out / "N2/partie")
        for k, a in enumerate(j["actions"][:i]):
            im, film = lab.play(a, purpose="acces_dernier_embranchement")
            if not np.array_equal(im, z["images"][k + 1]) or not np.array_equal(film, z[f"film_{k + 1}"]):
                raise ValueError("Accès N2 divergent")
        anchor = m.position(lab.image)
        offres = []
        # Après exploration bornée, retour recalculé depuis observations ; aucune action7.
        plan = d["plan"]
        phase = "branche"
        while newcount < 16:
            cur = {n: cs[n] for n in learner.actives()}
            b = modele(lab.image, h, cur, lab.actions_disponibles)
            target = ((anchor[0] - b.origin[0]) // m.pas, (anchor[1] - b.origin[1]) // m.pas)
            back = retour(b, b.depart, target)
            if back is None:
                raise ValueError("Retrait devenu non démontré")
            if not plan:
                phase = "retour"
                plan = back
                if not plan:
                    status = "branche_et_retour_verifies"
                    break
            a = plan[0]
            a = tuple(a) if isinstance(a, list) else a
            t = b.pas(b.depart, a)
            if t is None or any(v != "continue" for v in t[2]):
                raise ValueError("Plan réfuté avant action")
            safeguard = retour(b, t, target)
            if safeguard is None or newcount + 1 + len(safeguard) > 16:
                raise ValueError("Action compromet retrait ou budget")
            a = json.loads(json.dumps(a, default=int))
            before = lab.image.copy()
            key = cle(before, a)
            if phase == "branche" and key in known:
                raise ValueError("Ancienne expérience")
            offres.append(list(lab.actions_disponibles))
            predictions = dict(zip(cur, t[2]))
            sauver(
                out / f"avant_{newcount + 1}.json",
                {
                    "action": a,
                    "phase": phase,
                    "retour_apres_action": safeguard,
                    "predictions": predictions,
                    "offre": lab.actions_disponibles,
                },
            )
            im, film = lab.play(a, purpose=phase)
            newcount += 1
            known.add(key)
            issue = issue_sdk(lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 1)
            obs = learner.observer(scenes_film(before, film, m), issue, str(newcount), True, predictions)
            hist.append({"action": a, "phase": phase, "observation": obs})
            if lab.finished:
                status = "victoire_N2" if lab.won else "defaite"
                break
            h.observer(before, a, im, film, issue_observee=issue)
            if not h.actives():
                raise ValueError("Dynamique réfutée")
            # Ce test conserve sa destination et vérifie chaque tronçon, puis recalcule le retrait.
            plan = plan[1:] if phase == "branche" else []
    except (ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        status = "refus:" + repr(exc)
    finally:
        bilan = {
            "statut": status,
            "coups_N1": len(access.rows),
            "coups_N2": len(lab.rows) if lab is not access else 0,
            "coups_acces_N2": min(i, len(lab.rows)) if lab is not access else 0,
            "nouveaux_coups": newcount,
            "initialisations": 1,
            "resets": 0,
            "hypotheses_actives": learner.actives(),
            "sources_inchangees": hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")},
        }
        sauver(out / "bilan.json", bilan)
        sauver(out / "historique.json", hist)
        sauver(out / "dynamique.json", h.journal)
        print(json.dumps(bilan))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--executer", action="store_true")
    args = ap.parse_args()
    main(args.sortie, args.executer)
