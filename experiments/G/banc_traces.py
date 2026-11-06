"""[G] 0 écart et vitesse de `sim_genere` sur les trajectoires réelles des 20 jeux (`experiments/T3.1/traces_sim.json.gz`,
parties R0 rejouées, aucun jeu témoin).
Contrôle, à chaque coup, entre la référence (`ProgrammeCompile` + `sim_rapide.cloner` + `cle_complete`) et G
(`ProgrammeGenere` + `sim_genere.cloner` + `sim_genere.cle_complete`) : même exception, même issue, même image (complète
si canevas), même clé (`cle_complete` des deux côtés, et clé G = clé de référence).
Vitesse : un « nœud » = copie + coup + clé, comme dans la recherche ; passes répétées ≥ 1 s, temps CPU ; ref, G1 (copie +
clé seulement), G (tout). → `experiments/G/banc_traces.json`.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_traces.py [jeux…]"""
import json
import sys
import time
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "experiments/T3.1"))
from bench_sim_rapide import TEMOINS, charger_traces, regles, scene_de_json

from chrysalide.arc3 import sim_genere as g
from chrysalide.arc3 import sim_rapide as sr
from chrysalide.arc3.logique.plan_langage import cle_complete

MODES = {"ref": (sr.ProgrammeCompile, sr.cloner, cle_complete), "G1": (sr.ProgrammeCompile, g.cloner, g.cle_complete),
         "G": (g.ProgrammeGenere, g.cloner, g.cle_complete)}


def _im(sc):
    return sr.image_complete(sc) if getattr(sc, "canevas", None) else sr.image(sc)


def controle(jeu, segs):
    """→ (coups, écarts, premier écart)."""
    pr, pg = sr.ProgrammeCompile(regles(jeu)), g.ProgrammeGenere(regles(jeu))
    n, ecarts, premier = 0, 0, None
    for seg in segs:
        sr_, sg = scene_de_json(seg["scene"]), scene_de_json(seg["scene"])
        for a in seg["coups"]:
            a = tuple(a)
            sr_, pr.etat = sr.cloner(sr_, pr.etat)
            sg, pg.etat = g.cloner(sg, pg.etat)
            er = eg = None
            try:
                pr.step(sr_, a)
            except Exception as x:  # noqa: BLE001
                er = type(x).__name__
            try:
                pg.step(sg, a)
            except Exception as x:  # noqa: BLE001
                eg = type(x).__name__
            k = cle_complete(sr_, pr.etat)
            ok = er == eg and sr_.issue == sg.issue and k == cle_complete(sg, pg.etat) == g.cle_complete(sg, pg.etat) \
                and np.array_equal(_im(sr_), _im(sg))
            if not ok:
                ecarts += 1
                premier = premier or {"coup": n, "action": a, "exc": [er, eg]}
            n += 1
    return n, ecarts, premier


def vitesse(jeu, segs, mode):
    P, cl, cle = MODES[mode]
    rep, t, m = 0, 0.0, 0
    while t < 1.0:
        prog = P(regles(jeu))
        for seg in segs:
            sc = scene_de_json(seg["scene"])
            t0 = time.process_time()
            for a in seg["coups"]:
                sc, prog.etat = cl(sc, prog.etat)
                try:
                    prog.step(sc, tuple(a))
                except Exception:  # noqa: BLE001, S110
                    pass
                cle(sc, prog.etat)
                m += 1
            t += time.process_time() - t0
        rep += 1
    return round(m / t)


def main(jeux):
    traces = charger_traces()
    res = {}
    for jeu in sorted(traces):
        if jeu in TEMOINS or (jeux and jeu not in jeux):
            continue
        n, ec, prem = controle(jeu, traces[jeu])
        r = {"coups": n, "ecarts": ec, "premier_ecart": prem}
        for _ in range(2):  # deux passes alternées, meilleure gardée (Mac partagé)
            for mode in MODES:
                r[mode] = max(r.get(mode, 0), vitesse(jeu, traces[jeu], mode))
        r["gain_G1"], r["gain"] = round(r["G1"] / r["ref"], 2), round(r["G"] / r["ref"], 2)
        res[jeu] = r
        print(jeu, json.dumps(r), flush=True)
    sortie = RACINE / "experiments/G/banc_traces.json"
    anciens = json.loads(sortie.read_text()) if sortie.exists() and jeux else {}
    sortie.write_text(json.dumps({**anciens, **res}, indent=1))
    gains = sorted(r["gain"] for r in res.values())
    print("écarts totaux", sum(r["ecarts"] for r in res.values()), "gain médian", gains[len(gains) // 2],
          "min", gains[0], "max", gains[-1])


if __name__ == "__main__":
    main(sys.argv[1:])
