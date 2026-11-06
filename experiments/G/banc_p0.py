"""[G] Banc P0 apparié, avec et sans `sim_genere` (CW-291, point 3) : `experiments/T3.0/plafonds.p0` tel quel (fichier non
modifié), 20 jeux × niveaux 1-3, recherche `but` par défaut. Les deux bras sont mêlés dans le MÊME lot (même charge) ; le
chronomètre de `plafonds` lit le temps CPU du processus (`time.time` remplacé dans ce module seulement, leçon CCM-004-F).
Chaque plan trouvé est rejoué dans le vrai jeu par `plafonds` (champ `gagne`).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_p0.py NOEUDS SECONDES PROCESSUS [recherche] [jeux] [niveaux]
→ experiments/G/p0_<recherche>_<noeuds>_<secondes>.json (une ligne par tâche et par bras) + résumé apparié."""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


class _TempsCPU:
    """`time` vu par plafonds : `time()` = temps CPU du processus, le reste inchangé."""

    def __getattr__(self, n):
        return getattr(time, n)

    @staticmethod
    def time():
        return time.process_time()


def _init():
    import os
    os.chdir(RACINE / "experiments/T3.0")
    sys.path.insert(0, str(RACINE / "experiments/T3.0"))
    sys.path.insert(0, str(RACINE))
    import plafonds
    plafonds.time = _TempsCPU()


def _tache(t):
    bras, args = t
    import plafonds

    from chrysalide.arc3 import sim_genere as g
    if bras in ("G", "G2"):
        g.installer(force=True, plate=bras == "G2")
    else:
        g.desinstaller()
    t0, m0 = time.process_time(), time.time()
    print(f"[début] {bras} {args[0]} N{args[1]} {time.strftime('%H:%M:%S')}", file=sys.stderr, flush=True)
    r = plafonds._un(args)
    print(f"[fin] {bras} {args[0]} N{args[1]} cpu {time.process_time() - t0:.1f} mural {time.time() - m0:.1f}",
          file=sys.stderr, flush=True)
    return {**r, "bras": bras, "cpu": round(time.process_time() - t0, 1)}


def main():
    noeuds, secondes, proc = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
    recherche = sys.argv[4] if len(sys.argv) > 4 else "but"
    regles = RACINE / "experiments/T3.1/regles"
    jeux = sys.argv[5].split(",") if len(sys.argv) > 5 and sys.argv[5] != "tous" else \
        sorted(p.stem for p in regles.glob("*.json") if "_" not in p.stem)
    jeux = [j for j in jeux if j not in TEMOINS]
    niveaux = [int(x) for x in (sys.argv[6] if len(sys.argv) > 6 else "1,2,3").split(",")]
    import os
    bras = os.environ.get("G_BRAS", "ref,G").split(",")  # G2 : clé plate (CHRYS_BACKEND_TABLEAUX=2)
    taches = [(b, (j, k, noeuds, secondes, recherche)) for j in jeux for k in niveaux for b in bras]
    with Pool(proc, initializer=_init) as pool:
        res = []
        for r in pool.imap_unordered(_tache, taches, chunksize=1):
            res.append(r)
            print(json.dumps({x: r.get(x) for x in ("bras", "jeu", "niveau", "gagne", "noeuds", "etats", "cpu",
                                                     "raison")}, ensure_ascii=False), flush=True)
    out = RACINE / f"experiments/G/p0_{recherche}_{noeuds}_{int(secondes)}.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    par = {(r["jeu"], r["niveau"], r["bras"]): r for r in res}
    cles = sorted({(j, k) for j, k, _ in par})
    gagne = {b: sum(bool(par.get((j, k, b), {}).get("gagne")) for j, k in cles) for b in bras}
    for b in bras[1:]:
        print(b, "identique à ref (nœuds, états, plan, gagné) :",
              sum(all(par.get((j, k, b), {}).get(x) == par.get((j, k, "ref"), {}).get(x) for x in ("noeuds", "etats", "plan", "gagne"))
                  for j, k in cles), "/", len(cles))
    plus = [f"{j} N{k}" for j, k in cles if par.get((j, k, "G"), {}).get("gagne") and not par.get((j, k, "ref"), {}).get("gagne")]
    moins = [f"{j} N{k}" for j, k in cles if par.get((j, k, "ref"), {}).get("gagne") and not par.get((j, k, "G"), {}).get("gagne")]
    vit = sorted(par[(j, k, "G")]["noeuds"] / max(par[(j, k, "G")]["cpu"], 1e-9)
                 / (par[(j, k, "ref")]["noeuds"] / max(par[(j, k, "ref")]["cpu"], 1e-9))
                 for j, k in cles if all(par.get((j, k, b), {}).get("noeuds") for b in ("ref", "G"))
                 and par[(j, k, "ref")]["cpu"] > 5)
    print(f"P0 {recherche} {noeuds} nœuds {secondes} s CPU : gagnés {gagne} sur {len(cles)} ;"
          f" + {plus} ; − {moins} ; nœuds/s G/ref médiane ×{vit[len(vit) // 2]:.2f} sur {len(vit)} niveaux" if vit else "")


if __name__ == "__main__":
    main()
