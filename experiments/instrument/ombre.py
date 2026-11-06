# SPDX-License-Identifier: MIT-0
"""Vérificateur du moteur EN MODE OMBRE sur les coups de Franzen (CW-226.3, CW-228.3 c), sans veto, hors ligne.
Trajectoires : les parties déjà jouées (artefacts *_events.jsonl d'un bloc, 20 jeux publics non témoins), découpées par
niveau et par vie. Avant chaque coup t du modèle (t ≥ 5 dans le segment), le moteur rend un verdict sur le PASSÉ seul :
  R1 « déjà vu sans effet » : même image exacte et même action déjà jouées dans ce segment, sans changement → « contredit » ;
  R2 « prédit sans effet » : la prédiction AVEC ABSTENTION de C (prediction.predire) est acceptée et ne change rien ;
  sinon « inconnu » (abstention de C) ou « confirmé ».
Vérité : `board_changed` du harnais. Erreur évitable = coup sans effet. Faux positif = coup signalé « sans effet » qui a
changé l'image. Usage : uv run python experiments/instrument/ombre.py <dossier_artefacts> [processus=6] [r=10]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
NUMS = {"ACTION1": 1, "ACTION2": 2, "ACTION3": 3, "ACTION4": 4, "ACTION5": 5, "ACTION7": 7}


def segments(f):
    """[(grilles, actions, changes)] par niveau et par vie ; changes[t] = board_changed du coup t."""
    out, g, a, ch = [], None, [], []
    for ligne in f.read_text().splitlines():
        e = json.loads(ligne)
        if e.get("type") == "initial":
            g, a, ch = [np.asarray(e["board"])], [], []
            continue
        if e.get("type") != "action":
            continue
        nom = e.get("action_name")
        if nom == "ACTION6":
            aff = e["action_display"]
            r, c = (int(x.split("=")[1]) for x in aff[aff.index("(") + 1:-1].split(", "))
            act = ("clic", c, r)
        else:
            act = NUMS.get(nom)
        fin = e.get("level_completed") or e.get("game_over")
        if g is not None and act is not None:
            if fin:
                a.append(act)
                ch.append(bool(e.get("board_changed")))
                if len(a) > 1:
                    out.append((g, a[:-1], ch[:-1]))
                g, a, ch = [np.asarray(e["board"])], [], []  # le segment suivant repart de l'image observée
                continue
            a.append(act)
            ch.append(bool(e.get("board_changed")))
            g.append(np.asarray(e["board"]))
    if g is not None and a:
        out.append((g, a, ch))
    return out


def verdicts(seg, r=10, debut=5):
    from chrysalide.arc3.logique.faits import Trajectoire
    from chrysalide.arc3.logique.induction import induire
    from chrysalide.arc3.logique.prediction import Connaissance, predire
    grilles, actions, changes = seg
    vus, th, lignes = {}, None, []
    for t in range(len(actions)):
        cle = (grilles[t].tobytes(), actions[t])
        r1 = vus.get(cle) is False  # même image, même action, déjà jouée sans effet
        r2, raison = None, None
        if t >= debut and len(grilles) > t:
            tr = Trajectoire([x.tolist() for x in grilles[:t + 1]], actions[:t])
            if th is None or (t - debut) % r == 0:
                th, _ = induire([(tr, None, None)], limite_s=20)
            th.hors_jeu = tr.exclues
            pred, raison = predire(th, Connaissance(tr, range(t)), tr.etats[t], actions[t], tr.taille)
            r2 = None if pred is None else set(pred) == set(tr.etats[t])
        # vérité au niveau des OBJETS (interface masquée : la barre de coups change à chaque coup, même inutile)
        objets = None
        if t >= debut and len(grilles) > t + 1:
            objets = set(tr.etat(grilles[t + 1])) != set(tr.etats[t])
        lignes.append({"t": t, "change": changes[t], "change_objets": objets, "r1": r1, "r2": r2, "abstention": raison})
        if len(grilles) > t + 1:
            vus[cle] = bool(changes[t])
    return lignes


def jeu(f):
    try:
        return f.name.split("-")[0], [verdicts(s, R) for s in segments(f)], None
    except Exception as e:  # noqa: BLE001 — échec compté
        return f.name.split("-")[0], [], f"{type(e).__name__}: {e}"[:200]


R = 10


def main(dossier, proc=6, r=10):
    global R
    R = int(r)
    fs = [f for f in sorted(Path(dossier).glob("*_events.jsonl")) if f.name.split("-")[0] not in TEMOINS]
    res, tot = {}, Counter()
    with Pool(int(proc)) as p:
        for gid, segs, err in p.imap_unordered(jeu, fs):
            c = Counter()
            for s in segs:
                for x in s:
                    c["coups"] += 1
                    c["sans_effet"] += not x["change"]
                    if x["change_objets"] is not None:
                        c["juges_objets"] += 1
                        c["sans_effet_objets"] += not x["change_objets"]
                        if x["r2"]:
                            c["r2_vrai_objets"] += not x["change_objets"]
                            c["r2_faux_positif_objets"] += x["change_objets"]
                    for k in ("r1", "r2"):
                        if x[k]:
                            c[f"{k}_signale"] += 1
                            c[f"{k}_vrai"] += not x["change"]
                            c[f"{k}_faux_positif"] += x["change"]
                    c["r2_juge"] += x["r2"] is not None
                    if x["r1"] or x["r2"]:
                        c["union_signale"] += 1
                        c["union_vrai"] += not x["change"]
            fp = [{"segment": i, **x} for i, sg in enumerate(segs) for x in sg if x["r2"] and x["change_objets"]][:8]
            res[gid] = {"erreur": err, **c, "exemples_faux_positifs_r2": fp}
            tot.update(c)
            print(gid, dict(c), err or "", flush=True)
    sortie = Path("experiments/instrument/ombre_" + Path(dossier).parts[-3] + ".json")
    sortie.write_text(json.dumps({"total": tot, "jeux": res}, indent=1, ensure_ascii=False))
    print("TOTAL", dict(tot))


if __name__ == "__main__":
    main(*sys.argv[1:])
