"""Prépare un plan ou son premier préfixe discriminant depuis l'historique réel."""

import argparse
import copy
import json
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / "paquet"), str(ICI)]
from chaine_coherente import Chaine
from plan_selection_dynamique import chercher
from selection_observee import SelectionObservee

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import NOMS
from chrysalide.langue import vers_python


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    args = ap.parse_args()
    args.sortie.mkdir(parents=True, exist_ok=False)
    gs = np.load(args.source.with_suffix(".npz"))["images"]
    actions = [r["action"] for r in json.loads(args.source.with_suffix(".json").read_text())["rows"]]
    lots = [
        {"actions": [{"action": NOMS[a]} if isinstance(a, int) else {"action": "MOUSE", "row": a[2], "col": a[1]}]}
        for a in actions
    ]
    z = np.load(args.source.with_suffix(".npz"))
    films = [z[f"film_{k}"] for k in range(1, len(actions) + 1)]
    v = SelectionObservee(gs, actions, films=films)
    variantes = [("observe", v)]
    variantes.extend((mode, SelectionObservee(gs, actions, contact=mode, films=films)) for mode in ("pas", "glisse", "sortie"))
    if v.incertains:
        variantes.append(("surface_inconnue_franchissable", SelectionObservee(gs, actions, v.incertains, films=films)))
    controles, candidats, choix = [], [], None
    for nom, vue in variantes:
        prog = vue.programme()
        chaine = Chaine(
            vue,
            prog,
            gs.tolist(),
            lots,
            [(NOMS[k],) for k in range(1, 5)] + [("MOUSE", y + vue.my, x + vue.mx) for x, y in vue.pos[-1]],
            films=films,
        )
        ctrl, etat = chaine.rejouer()
        if etat is None:
            controles.append({"nom": nom, "controle": ctrl, "refute": True})
            continue
        plan = chaine.proposer(secondes=3)
        if plan["statut"] != "plan_simule_valide":
            chemin, infos = chercher(chaine, vue)
            if chemin is not None:
                plan = {"statut": "plan_simule_valide", "plan": {"actions": chemin}, "recherche_dynamique": infos}
            else:
                plan["recherche_dynamique"] = infos
        controles.append({"nom": nom, "controle": ctrl, "plan": plan})
        (args.sortie / f"{nom}.py").write_text(vers_python(prog))
        (args.sortie / f"{nom}.json").write_text(json.dumps(vue.signature_observation(), indent=2))
        pc = Programme(prog)
        sc = vue.scene(gs[0])
        for a in actions:
            pc.step(sc, (NOMS[a],) if isinstance(a, int) else ("MOUSE", a[2], a[1]))
        if not np.array_equal(vue.rendu(sc), vue.vue(gs[-1])):
            raise ValueError("État simulé différent de la dernière observation")
        candidats.append((nom, vue, pc, sc))
        if choix is None and plan["statut"] == "plan_simule_valide":
            choix = plan["plan"]["actions"]
    (args.sortie / "controles.json").write_text(json.dumps(controles, indent=2))
    if choix is None and len(candidats) > 1:
        # Recherche d'une expérience, sans prétendre avoir un plan gagnant.
        queue = deque([([copy.deepcopy(sc) for _, _, _, sc in candidats], [])])
        vus = set()
        debut = time.monotonic()
        noeuds = 0
        while queue and time.monotonic() - debut < 15 and noeuds < 5000:
            scenes, prefixe = queue.popleft()
            noeuds += 1
            if len(prefixe) >= 12:
                continue
            acts = [(NOMS[k],) for k in range(1, 5)]
            acts += [("MOUSE", o["y"] + v.my, o["x"] + v.mx) for o in scenes[0].sprites if "piece" in o.get("tags", [])]
            for a in acts:
                suivants = [copy.deepcopy(sc) for sc in scenes]
                cles = []
                for (_, vue, pc, _), sc in zip(candidats, suivants):
                    pc.step(sc, a)
                    cles.append((vue.rendu(sc).tobytes(), sc.issue))
                if len(set(cles)) > 1:
                    choix = prefixe + [list(a)]
                    break
                cle = cles[0]
                if cle not in vus and suivants[0].issue is None:
                    vus.add(cle)
                    queue.append((suivants, prefixe + [list(a)]))
            if choix is not None:
                break
        (args.sortie / "recherche_experience.json").write_text(
            json.dumps({"noeuds": noeuds, "secondes": time.monotonic() - debut, "prefixe": choix}, indent=2)
        )
    if choix is None:
        print("Aucun plan ni expérience discriminante dans le budget")
        return
    predictions, coups = [], []
    for a in choix[:12]:
        ligne = []
        for nom, vue, pc, sc in candidats:
            pc.step(sc, tuple(a))
            ligne.append({"nom": nom, "image": vue.rendu(sc).tolist(), "fin": sc.issue is not None})
        predictions.append(ligne)
        coups.append(["clic", a[2], a[1]] if a[0] == "MOUSE" else next(k for k, n in NOMS.items() if n == a[0]))
        if any(h["image"] != ligne[0]["image"] or h["fin"] != ligne[0]["fin"] for h in ligne[1:]):
            break
    exp = {
        "question": "Tester le premier désaccord entre modèles issus du film, puis replanifier",
        "actions": coups,
        "predictions": predictions,
        "hud": sorted(map(list, v.hud)),
    }
    (args.sortie / "experience.json").write_text(json.dumps(exp))
    print(json.dumps({"actions": coups, "hypotheses": [n for n, *_ in candidats]}))


if __name__ == "__main__":
    main()
