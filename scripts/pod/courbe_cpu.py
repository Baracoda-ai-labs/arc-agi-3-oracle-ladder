# SPDX-License-Identifier: MIT-0
"""SUR LE POD (CW-039/045) : courbe de montée en charge CPU de la voie 2 (graphe + BFS, explorateur « retour » du banc T2.3).
N processus jouent chacun les 25 jeux publics (1000 coups max) ; on mesure coups/s au total et PAR CŒUR, pour extrapoler à
Kaggle. Usage : python courbe_cpu.py <dossier environment_files> <sortie.json> [1,2,4,8,16,32]"""
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def un(args):
    envs, graine = args
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "arc3"))
    import banc
    from arc_agi import Arcade, OperationMode
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs)
    sc, n, t0 = arc.open_scorecard(), 0, time.perf_counter()
    for e in sorted(x.game_id for x in arc.get_environments() if x.game_id[:4] not in {"vc33", "tu93", "wa30", "s5i5", "cn04"}):  # témoins jamais joués
        n += banc.jouer(arc, sc, e, "retour", graine, 1000)["actions"]
    return n, time.perf_counter() - t0


if __name__ == "__main__":
    envs, sortie = sys.argv[1], sys.argv[2]
    paliers = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,2,4,8,16,32").split(",")]
    coeurs = len(os.sched_getaffinity(0))
    res = []
    for p in paliers:
        t0 = time.perf_counter()
        with Pool(p) as pool:
            r = pool.map(un, [(envs, g) for g in range(p)])
        mur = time.perf_counter() - t0
        coups = sum(x[0] for x in r)
        res.append({"processus": p, "coups": coups, "mur_s": round(mur, 1), "coups_par_s": round(coups / mur),
                    "coups_par_s_par_coeur": round(coups / mur / p)})
        print(json.dumps(res[-1]), flush=True)
    Path(sortie).write_text(json.dumps({"affinite_coeurs": coeurs, "cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip()
                                        if Path("/sys/fs/cgroup/cpu.max").exists() else "?", "paliers": res}, indent=1))
