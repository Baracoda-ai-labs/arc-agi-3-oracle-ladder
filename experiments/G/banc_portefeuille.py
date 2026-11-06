"""[G] CW-304 étape 2 — portefeuille de recherches : chaque stratégie avec le budget COMPLET (même nœuds, mêmes secondes CPU)
sur P0 (20 jeux × N1-3) et les 13 frontières de `banc_rates.py`, via `plafonds._un` (fichier non modifié ; G allumé).
Sortie : victoires par stratégie, victoires EXCLUSIVES (gagnées par cette seule stratégie), et l'union. Le partage du budget
(portefeuille à temps total égal à la référence) se calcule ensuite sur ces données.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_portefeuille.py NOEUDS SECONDES PROCESSUS [strategies]
→ experiments/G/portefeuille_<noeuds>_<secondes>.json"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_p0 import RACINE, TEMOINS, _TempsCPU
from banc_p0 import _init as _init_p0

STRATEGIES = ["but", "langage_but", "langage_paliers", "langage_generique", "compile_but", "iw1", "iw2", "largeur"]
FRONTIERES = [("bp35", 2), ("dc22", 4), ("g50t", 1), ("ka59", 4), ("lf52", 3), ("ls20", 4), ("m0r0", 6), ("re86", 5),
              ("sc25", 5), ("sk48", 2), ("sp80", 4), ("su15", 4), ("tr87", 6)]  # banc_rates.R0 : 1er niveau raté


def _init():
    """Comme banc_p0 (temps CPU dans plafonds), et aussi dans les planificateurs du langage (budgets comparables)."""
    _init_p0()
    from chrysalide.arc3.logique import plan_generique, plan_langage
    plan_langage.time = plan_generique.time = _TempsCPU()


def _tache(t):
    import plafonds
    strat, args = t
    t0 = time.process_time()
    print(f"[début] {strat} {args[0]} N{args[1]} {time.strftime('%H:%M:%S')}", file=sys.stderr, flush=True)
    r = plafonds._un(args)
    return {**r, "strategie": strat, "cpu": round(time.process_time() - t0, 1)}


def main():
    noeuds, secondes, proc = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
    strats = sys.argv[4].split(",") if len(sys.argv) > 4 else STRATEGIES
    regles = RACINE / "experiments/T3.1/regles"
    jeux = [p.stem for p in sorted(regles.glob("*.json")) if "_" not in p.stem and p.stem not in TEMOINS]
    niveaux = sorted({(j, k) for j in jeux for k in (1, 2, 3)} | set(FRONTIERES))
    taches = [(s, (j, k, noeuds, secondes, s)) for j, k in niveaux for s in strats]
    with Pool(proc, initializer=_init) as pool:
        res = []
        for r in pool.imap_unordered(_tache, taches, chunksize=1):
            res.append(r)
            print(json.dumps({x: r.get(x) for x in ("strategie", "jeu", "niveau", "gagne", "noeuds", "cpu", "raison")},
                             ensure_ascii=False), flush=True)
    (RACINE / f"experiments/G/portefeuille_{noeuds}_{int(secondes)}.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False, default=str))
    gagne = {}
    for r in res:
        if r.get("gagne"):
            gagne.setdefault((r["jeu"], r["niveau"]), set()).add(r["strategie"])
    fr = set(FRONTIERES)
    for s in strats:
        tous = [k for k, v in gagne.items() if s in v]
        excl = [k for k, v in gagne.items() if v == {s}]
        print(f"{s}: {len(tous)} gagnés ({sum(k in fr for k in tous)} frontières) ; exclusifs {sorted(excl)}")
    print(f"union : {len(gagne)} niveaux, dont frontières {sorted(k for k in gagne if k in fr)}")


if __name__ == "__main__":
    main()
