"""[G] Contrôle « rien perdu » de CHRYS_CLE_MONOTONE (CCM-012-G, CCM-297-A) : P0 (20 jeux × N1-3) + 13 frontières,
`langage_but` et `langage_paliers` (les recherches qui passent par `compiler=True`), drapeau éteint contre allumé, bras
mêlés dans le même lot, temps CPU (planificateurs du langage compris). Chaque plan est rejoué dans le vrai jeu.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_monotone.py NOEUDS SECONDES PROCESSUS → p0_monotone_*.json"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_portefeuille import FRONTIERES, RACINE, TEMOINS, _init

STRATS = ("langage_but", "langage_paliers")


def _tache(t):
    import plafonds

    from chrysalide.arc3.logique import plan_langage
    bras, args = t
    plan_langage.CLE_MONOTONE = bras == "monotone"
    t0 = time.process_time()
    r = plafonds._un(args)
    return {**r, "bras": bras, "strategie": args[4], "cpu": round(time.process_time() - t0, 1)}


def main():
    noeuds, secondes, proc = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
    jeux = [p.stem for p in sorted((RACINE / "experiments/T3.1/regles").glob("*.json"))
            if "_" not in p.stem and p.stem not in TEMOINS]
    niveaux = sorted({(j, k) for j in jeux for k in (1, 2, 3)} | set(FRONTIERES))
    taches = [(b, (j, k, noeuds, secondes, s)) for j, k in niveaux for s in STRATS for b in ("actuel", "monotone")]
    with Pool(proc, initializer=_init) as pool:
        res = []
        for r in pool.imap_unordered(_tache, taches, chunksize=1):
            res.append(r)
            print(json.dumps({x: r.get(x) for x in ("bras", "strategie", "jeu", "niveau", "gagne", "noeuds", "cpu",
                                                     "raison")}, ensure_ascii=False), flush=True)
    (RACINE / f"experiments/G/p0_monotone_{noeuds}_{int(secondes)}.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False, default=str))
    par = {(r["jeu"], r["niveau"], r["strategie"], r["bras"]): bool(r.get("gagne")) for r in res}
    for s in STRATS:
        cles = sorted({(j, k) for j, k, st, _ in par if st == s})
        a = {c for c in cles if par.get((*c, s, "actuel"))}
        m = {c for c in cles if par.get((*c, s, "monotone"))}
        print(f"{s} : actuel {len(a)}, monotone {len(m)} ; perdus {sorted(a - m)} ; gagnés en plus {sorted(m - a)}")


if __name__ == "__main__":
    main()
