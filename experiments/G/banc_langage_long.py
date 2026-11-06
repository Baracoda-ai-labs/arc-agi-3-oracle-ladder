"""[G] `langage_but` (planificateur du moteur, clé actuelle) à grand budget sur les frontières non gagnées : temps CPU,
plans rejoués dans le vrai jeu. Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_langage_long.py NOEUDS SECONDES
PROCESSUS jeu:niveau,… → experiments/G/langage_long_<noeuds>_<secondes>.json"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_portefeuille import RACINE, _init


def _tache(args):
    import plafonds
    t0 = time.process_time()
    r = plafonds._un(args)
    return {**r, "cpu": round(time.process_time() - t0, 1)}


def main():
    noeuds, secondes, proc = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
    paires = [(x.split(":")[0], int(x.split(":")[1])) for x in sys.argv[4].split(",")]
    with Pool(proc, initializer=_init) as pool:
        res = []
        for r in pool.imap_unordered(_tache, [(j, k, noeuds, secondes, "langage_but") for j, k in paires], chunksize=1):
            res.append(r)
            print(json.dumps({x: r.get(x) for x in ("jeu", "niveau", "gagne", "noeuds", "plan", "cpu", "raison")}),
                  flush=True)
    (RACINE / f"experiments/G/langage_long_{noeuds}_{int(secondes)}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
