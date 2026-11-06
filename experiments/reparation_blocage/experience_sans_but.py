"""Sonde falsifiable sans cible : nouveauté et objets des outils existants."""

import argparse
import json
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / "paquet"), str(ICI)]
from chaine_coherente import Chaine
from ontologie_extensible import _familles
from perception_guidee import questions
from roles_observes import PerceptionRoles

from chrysalide.arc3.exploration import Explorateur
from chrysalide.arc3.masque import Masque
from chrysalide.arc3.moteur import NOMS


def proposer(images, actions, films, offre):
    masque = Masque()
    for a, b in pairwise(images):
        masque.observer(a.tolist(), b.tolist())
    hud = masque.cellules()

    def propre(g):
        g = g.copy()
        for y, x in hud:
            g[y, x] = 0
        return g

    gs = [propre(g) for g in images]

    def dictionnaire(a):
        return {"action": NOMS[a]} if isinstance(a, int) else {"action": "MOUSE", "row": a[2], "col": a[1]}

    ex = Explorateur(graine=0)
    for k, a in enumerate(actions):
        ex.noter(gs[k], dictionnaire(a), gs[k + 1])
    cands = ex.candidats(gs[-1], offre) if offre else []
    # N'autoriser aucune répétition (image normalisée, action), même avec effet.
    cands = [c for c in cands if ex.essais[(gs[-1].tobytes(), ex._cle(c))] == 0]
    diagnostic = {"but_requis": False, "modele_complet_valide": False, "candidats_non_repetes": len(cands)}
    noms = [("CLICK" if a == 6 else NOMS[a]) for a in offre if a == 6 or a in NOMS]
    f = _familles()
    signaux = f.signaux_depuis_objets([], noms)
    diagnostic["orientation"] = {
        "familles": f.reconnaitre(signaux),
        "roles_supposes": vars(signaux),
        "classification_revocable": True,
        "scores_non_calibres": True,
        "questions": [],
    }
    diagnostic["actions_offertes"] = noms
    try:
        v = PerceptionRoles(images, [a if isinstance(a, int) else 6 for a in actions])
        diagnostic["orientation"] = questions(v, noms)
        lots = [{"actions": [dictionnaire(a)]} for a in actions]
        c = Chaine(v, v.programme(), [g.tolist() for g in images], lots, [], films=films)
        ctrl, _ = c.rejouer()
        diagnostic.update(
            mobiles=len(v.mobiles), buts_candidats=len(v.buts), controle=ctrl, modele_complet_valide=bool(ctrl.get("rejeu"))
        )
    except (ValueError, KeyError, IndexError, TypeError) as e:
        diagnostic["perception_refus"] = str(e)
    if not cands:
        return None, diagnostic
    # Un nouveau type d'action avant d'autres lieux du même type ; puis ordre stable.
    from collections import Counter

    usages = Counter(dictionnaire(a)["action"] for a in actions)
    types = set(usages)
    changements = np.zeros(images[-1].shape, bool)
    for avant, film in zip(images, films):
        for frame in film:
            changements |= propre(frame) != propre(avant)
    points = np.argwhere(changements)

    def priorite(c):
        distance = 0
        if c["action"] == "MOUSE" and len(points):
            distance = int(np.min(np.abs(points[:, 0] - c["row"]) + np.abs(points[:, 1] - c["col"])))
        return (c["action"] in types, usages[c["action"]], distance, c["action"], c.get("row", -1), c.get("col", -1))

    cands.sort(key=priorite)
    c = cands[0]
    action = ["clic", c["col"], c["row"]] if c["action"] == "MOUSE" else next(k for k, n in NOMS.items() if n == c["action"])
    exp = {
        "question": "Cette action non essayée dans cet état change-t-elle le film ou seulement le HUD ?",
        "type": "sonde_sans_but",
        "autorisation": "experience_uniquement_pas_un_plan",
        "actions": [action],
        "hud": sorted(map(list, hud)),
        "predictions": [[{"nom": "aucun_effet_visible_hypothese_nulle", "image": images[-1].tolist(), "fin": False}]],
        "diagnostic": diagnostic,
        "but": "inconnu",
        "contrats_interroges": ["selection_clic", "bouton"] if c["action"] == "MOUSE" else ["deplacement", "blocage"],
        "mesures": ["pixels_modifies", "frames_intermediaires", "motifs_persistants"],
    }
    return exp, diagnostic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--offre", required=True)
    args = ap.parse_args()
    z = np.load(args.source.with_suffix(".npz"))
    actions = [r["action"] for r in json.loads(args.source.with_suffix(".json").read_text())["rows"]]
    exp, diag = proposer(list(z["images"]), actions, [z[f"film_{k}"] for k in range(1, len(actions) + 1)], json.loads(args.offre))
    args.sortie.with_suffix(".diagnostic.json").write_text(json.dumps(diag, indent=2))
    if exp:
        args.sortie.write_text(json.dumps(exp))
    print(json.dumps(diag))


if __name__ == "__main__":
    main()
