# SPDX-License-Identifier: MIT-0
"""F (CW-467.3, CW-468.1, CW-470.2, CW-472.2, CW-473.2) : AUTOPSIE des interventions de MoteurC dans P1 (T1b), hors
ligne, sans jouer un seul coup. Pour chaque intervention journalisée (`journal_jeu.jsonl`, étape « intervention ») :
  1. la fenêtre exacte vue par le moteur est reconstruite (`releve_moteur.tenter` : 40 derniers coups de la vie en cours,
     images de `partie.npz`) ; `MoteurC.proposer` est relancé → théorie, but, plan, simulateur (porte) ;
  2. FIDÉLITÉ : le plan reconstruit doit être identique aux coups réellement joués à partir du coup k ;
  3. 1ʳᵉ DIVERGENCE : après chaque coup du plan, rendu prédit par le simulateur contre image réelle (vue du moteur) ;
     au 1ᵉʳ désaccord, on garde les cases fausses (y, x, prédit, réel) et l'état `issue` du simulateur.
Aucune information d'évaluateur (vérité T4, oracle) n'entre ici : seulement ce que le moteur avait, et l'image réelle.
Mêmes réglages que le lanceur T1 (`T1_releve_p1/lancer_t1.sh`), plus `CHRYS_BUTS_MAX` si fourni.
Usage : CHRYS_FILMS_P1=3 CHRYS_G_NOUV=1 CHRYS_F_CLE=bande3 CHRYS_BUT_SUPPOSE=1 [CHRYS_BUTS_MAX=0] \\
        uv run python experiments/oracle/autopsie.py <run> <sortie.json> [jeu:niveau:coup,…]"""
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
W = R / "experiments/T1_releve_p1/paquet"
sys.path[:0] = [str(R), str(W / "livraison_p1/code")]
from agent_p1.releve_moteur import FENETRE, _lot, _vers_p1

from chrysalide.arc3.moteur import MoteurC, _code_c, nom_action, porte


def interventions(run):
    """[(jeu, niveau, coup, issue, coups exécutés)] des interventions journalisées."""
    out = []
    for jj in sorted(Path(run).glob("*/journal_jeu.jsonl")):
        issue = {}
        for x in map(json.loads, jj.read_text().splitlines()):
            if x.get("type") == "moteur" and x.get("etape") == "resultat":
                issue[(x["niveau"], x["coup"])] = (x.get("issue"), int(x.get("coups") or 0))
        out += [(jj.parent.name, n, k, i, c) for (n, k), (i, c) in sorted(issue.items())]
    return out


def norm(a):
    return tuple(a) if isinstance(a, list) else a


def autopsie(run, jeu, niv, k, issue=None, n_exec=None):
    d = Path(run) / jeu / f"N{niv}"
    ims = np.load(d / "partie.npz")["images"]
    acts = [norm(a) for a in json.loads((d / "partie.json").read_text())["actions"]]
    debut = max((t + 1 for t, a in enumerate(acts[:k]) if a == 0), default=0)
    a = acts[debut:k][-FENETRE:]
    imgs = ims[debut:k + 1][-(len(a) + 1):]
    grilles, lots = [np.asarray(g).tolist() for g in imgs], [_lot(x) for x in a]
    m = MoteurC(budget=30)
    t0 = time.process_time()
    r = m.proposer({"grilles": grilles, "lots": lots, "precedents": []})
    out = {"jeu": jeu, "niveau": niv, "coup": k, "fenetre": len(a), "cpu_s": round(time.process_time() - t0, 2),
           "but": m.infos.get("but_suppose") or None, "origine": m.infos.get("origine"),
           "theorie": (m.infos.get("theorie") or "")[:1200], "refus": m.infos.get("refus")}
    if not r:
        out["etat"] = "pas de plan à la reconstruction"
        return out
    plan = [_vers_p1(_code_c(x if "action" in x else x["actions"][0])) for x in r[0]]
    joues = acts[k:k + len(plan)]
    out.update(plan=[str(p) for p in plan], joues=[str(x) for x in joues],
               fidele=[norm(p) for p in plan] == joues[:len(plan)])
    p = porte(m, r[1], grilles, lots) if r[1] else None
    if p is None:
        out["etat"] = "porte : la théorie ne rejoue pas la fenêtre à la reconstruction"
        return out
    # On simule les coups RÉELLEMENT exécutés (le plan reconstruit peut différer : recherche bornée par le temps CPU).
    execs = acts[k:k + (n_exec or len(plan))]
    out["coups_executes"] = len(execs)
    prog, sc = copy.deepcopy(p)
    for i, x in enumerate(execs):
        if issue == "victoire" and i == len(execs) - 1:
            out.update(etat="victoire", pas=i + 1, predit_juste_avant=True)
            return out
        if k + i + 1 >= len(ims):
            out["etat"] = f"trace finie au coup {i} du plan"
            return out
        reel = np.asarray(m.vue(np.asarray(ims[k + i + 1]).tolist()))
        try:
            prog.step(sc, nom_action(_lot(x)["actions"][0]))
            pred = np.asarray(m.rendu(sc))
        except Exception as e:  # noqa: BLE001
            out.update(etat="divergence", pas=i + 1, cause_brute=f"simulateur : {type(e).__name__}: {e}"[:200])
            return out
        if sc.issue is not None or pred.shape != reel.shape or not np.array_equal(pred, reel):
            cases = [] if pred.shape != reel.shape else [[int(y), int(xx), int(pred[y, xx]), int(reel[y, xx])]
                                                        for y, xx in zip(*np.nonzero(pred != reel), strict=True)]
            out.update(etat="mort" if issue == "mort" and i == len(execs) - 1 else "divergence", pas=i + 1,
                       action=str(x), issue_simulee=sc.issue, n_cases=len(cases), cases=cases[:40],
                       forme=[list(pred.shape), list(reel.shape)])
            return out
    out["etat"] = "plan entier prédit juste"
    return out


def main():
    run, sortie = sys.argv[1], Path(sys.argv[2])
    sel = None
    if len(sys.argv) > 3:
        sel = {(j, int(n), int(c)) for j, n, c in (s.split(":") for s in sys.argv[3].split(","))}
    res = json.loads(sortie.read_text()) if sortie.exists() else {}
    for jeu, niv, k, issue, n_exec in interventions(run):
        if sel is not None and (jeu, niv, k) not in sel:
            continue
        cle = f"{jeu}:{niv}:{k}"
        try:
            r = autopsie(run, jeu, niv, k, issue, n_exec)
        except Exception as e:  # noqa: BLE001
            r = {"jeu": jeu, "niveau": niv, "coup": k, "etat": f"plantage {type(e).__name__}: {e}"[:200]}
        r["issue_reelle"] = issue
        res[cle] = r
        print(cle, issue, r.get("etat"), r.get("fidele"), r.get("pas"), r.get("n_cases"), flush=True)
        sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
