# SPDX-License-Identifier: MIT-0
"""CW-256 [session E] : tours par seconde, sur les solutions de tous les niveaux d'un échantillon de jeux (1 sur 10), pour :
interprété du langage (`langage.Programme` + `interpreteur_ps_v2.json`), compilé en fermetures (`sim_rapide.ProgrammeCompile`,
de A), psmoteur (Python pur), compilé en grilles de bits (`ps_compile.PartieCompilee`). Sans moteur ARC ni juge.
Usage : uv run python experiments/ps_langage/vitesse.py [pas=10]"""
import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parents[1]))
import expliquer as X  # noqa: E402
import juge_ps  # noqa: E402
import ps_compile as C  # noqa: E402
from chrysalide.arc3.langage import Programme  # noqa: E402
from chrysalide.arc3.sim_rapide import ProgrammeCompile  # noqa: E402

PS = {1: "up", 2: "down", 3: "left", 4: "right", 5: "action"}


def mesurer(jeu):
    f = X._module(jeu)
    cst = juge_ps.constantes_module(f)
    cst["FOND"] = int(next(l for l in f.read_text().splitlines() if l.startswith("FOND = ")).split()[-1])
    verite = json.loads(next((X.ENV / jeu).glob("*/verite.json")).read_text())
    j = C.P.Jeu(cst["SOURCE_PS"])
    jc = C.JeuCompile(j)
    texte = json.loads((ICI / "interpreteur_ps_v2.json").read_text())
    s, n = {"langage": 0.0, "sim_rapide": 0.0, "psmoteur": 0.0, "compile": 0.0}, 0
    for i, k in enumerate(cst["NIVEAUX_PS"]):
        sol = verite["niveaux"][i]["solution"]
        n += len(sol)
        for nom, cls in (("langage", Programme), ("sim_rapide", ProgrammeCompile)):
            t = dict(texte, niveau=juge_ps.donnees(f, niveaux=[k]))
            prog, sc = cls(t), X._scene(C.P.Partie(j, k), k, cst, True)
            t0 = time.perf_counter()
            for a in sol:
                prog.step(sc, (X.VERS_LANGAGE[PS[a]], None, None), 0)
            s[nom] += time.perf_counter() - t0
        for nom, mk in (("psmoteur", lambda: C.P.Partie(j, k)), ("compile", lambda: C.PartieCompilee(j, k, jc))):
            p = mk()
            t0 = time.perf_counter()
            for a in sol:
                p.tour(PS[a])
            s[nom] += time.perf_counter() - t0
    return n, s


if __name__ == "__main__":
    pas = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    jeux = sorted(d.name for d in X.ENV.iterdir() if d.is_dir())[::pas]
    tot, ntot = {}, 0
    for g in jeux:
        n, s = mesurer(g)
        ntot += n
        for k, v in s.items():
            tot[k] = tot.get(k, 0) + v
        print(g, n, "tours", {k: round(n / v) if v else None for k, v in s.items()}, "tours/s", flush=True)
    print(f"TOTAL {len(jeux)} jeux, {ntot} tours :", {k: round(ntot / v, 1) for k, v in tot.items()}, "tours/s ;",
          f"compilé / langage ×{tot['langage'] / tot['compile']:.0f}, compilé / sim_rapide ×{tot['sim_rapide'] / tot['compile']:.0f}")
