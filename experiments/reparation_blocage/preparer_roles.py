"""Ablations et plan avec prédictions avant toute exécution SDK."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / "paquet"), str(ICI)]
from chaine_coherente import Chaine
from roles_observes import PerceptionRoles

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import NOMS
from chrysalide.langue import vers_python


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--sans-ablation", action="store_true")
    args = ap.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    with np.load(args.source.with_suffix(".npz")) as z:
        gs = z["images"].copy()
    actions = [r["action"] for r in json.loads(args.source.with_suffix(".json").read_text())["rows"]]
    controles = []
    choix = None
    for decor, roles in [(True, True)] if args.sans_ablation else [(False, False), (True, False), (False, True), (True, True)]:
        v = PerceptionRoles(gs, actions, decor, roles)
        for cible in v.buts:
            p = v.programme(cible)
            c = Chaine(
                v,
                p,
                gs.tolist(),
                [{"actions": [{"action": NOMS[a]}]} for a in actions],
                [(NOMS[k],) for k in range(1, 5)],
                coups_deja_joues=len(actions),
                reserve=80,
            )
            ctrl, etat = c.rejouer()
            ligne = {"decor": decor, "roles": roles, "cible": cible, "controle": ctrl}
            if decor and roles and etat is not None:
                plan = c.proposer(secondes=3)
                ligne["plan"] = plan
                if choix is None and plan["statut"] == "plan_simule_valide":
                    choix = (v, p, plan)
            controles.append(ligne)
    (out / "controles.json").write_text(json.dumps(controles, indent=2))
    if choix:
        v, p, plan = choix
        (out / "programme.py").write_text(vers_python(p))
        (out / "preuves.json").write_text(json.dumps(v.signature_observation(), indent=2))
        pc = Programme(p)
        sc = v.scene(gs[0])
        for a in actions:
            pc.step(sc, (NOMS[a],))
        preds = []
        coups = []
        for a in plan["plan"]["actions"][:12]:
            pc.step(sc, tuple(a))
            coups.append(next(k for k, n in NOMS.items() if n == a[0]))
            preds.append(
                [{"nom": "modele_roles_et_but_hypothetique", "image": v.rendu(sc).tolist(), "fin": sc.issue is not None}]
            )
        exp = {
            "question": "Le déplacement prévu et le but de correspondance sont-ils confirmés ?",
            "actions": coups,
            "predictions": preds,
            "hud": sorted(map(list, v.hud)),
        }
        (out / "experience.json").write_text(json.dumps(exp))
        print(json.dumps({"plan": coups, "franchis": list(v.franchis), "devoiles": len(v.preuves_decor)}))
    else:
        print("Aucun plan admissible")


if __name__ == "__main__":
    main()
