# SPDX-License-Identifier: MIT-0
"""SUR LE POD (CW-125/126 P1-a) : montée en charge CPU des TROIS moteurs qui tourneraient sur les CPU de Kaggle.
  moteur : le vrai moteur arcengine (explorateur « retour » du banc T2.3, 20 jeux NON témoins, 300 coups) → coups/s ;
  sim    : le simulateur compilé du langage (sim_rapide, copie d'état + coup + rendu, traces R0 de 19 jeux) → états/s ;
  asp    : l'induction ASP de C via E4 (une partie sn00, politique refutation_exp, 150 coups) → parties/h.
Pour chaque palier N : N processus identiques en parallèle ; débit total et PAR PROCESSUS (la baisse par processus quand N
monte = contention). Usage : python courbe_cpu2.py <moteur|sim|asp> <sortie.json> [1,2,4,8,16]"""
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
ENVS = "/workspace/environment_files"


def moteur(_):
    sys.path.insert(0, str(RACINE / "experiments" / "arc3"))
    import banc
    from arc_agi import Arcade, OperationMode
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=ENVS)
    sc, n, t0 = arc.open_scorecard(), 0, time.perf_counter()
    for e in sorted(x.game_id for x in arc.get_environments() if x.game_id[:4] not in TEMOINS):
        n += banc.jouer(arc, sc, e, "retour", 0, 300)["actions"]
    return n, time.perf_counter() - t0


def sim(_):
    sys.path.insert(0, str(RACINE / "experiments" / "T3.1"))
    import bench_sim_rapide as B
    traces, n, t = B.charger_traces(), 0, 0.0
    for jeu, segs in traces.items():
        dt, k, _ = B.rejouer(jeu, segs, True, True, True)
        n, t = n + k, t + dt
    return n, t


def asp(_):
    sys.path.insert(0, str(RACINE / "experiments" / "T2.9"))
    import e4
    t0 = time.perf_counter()
    e4.tache(("sn00-" + _sn00(), 0, "refutation_exp", 150))
    return 1, time.perf_counter() - t0


def _sn00():
    import json as j
    sols = j.loads((RACINE / "experiments/T2.8/synth_envs/solutions.json").read_text())
    return next(g for g in sols if g.startswith("sn00")).split("-", 1)[1]


if __name__ == "__main__":
    mode, sortie = sys.argv[1], sys.argv[2]
    paliers = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,2,4,8,16").split(",")]
    f = {"moteur": moteur, "sim": sim, "asp": asp}[mode]
    res = {"mode": mode, "coeurs_visibles": len(os.sched_getaffinity(0)), "paliers": []}
    for n in paliers:
        t0 = time.perf_counter()
        with Pool(n) as p:
            r = p.map(f, range(n))
        mur = time.perf_counter() - t0
        unites = sum(k for k, _ in r)
        par_proc = sum(k / t for k, t in r) / n
        res["paliers"].append({"n": n, "unites": unites, "mur_s": round(mur, 1), "debit_total_par_s": round(unites / mur, 2),
                               "debit_par_processus_par_s": round(par_proc, 2)})
        print(json.dumps(res["paliers"][-1]), flush=True)
        Path(sortie).write_text(json.dumps(res, indent=1))
