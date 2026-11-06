"""[G] Contrôle et mesure de `sim_genere` sur une recherche P0 réelle (`experiments/T3.0/plafonds.p0`, fichier non modifié).
- `controle` : la recherche tourne sur les copies de `sim_genere.cloner` ; à CHAQUE copie, la clé de la copie est comparée à
  celle de `sim_rapide.cloner` (même parent) ; à CHAQUE clé demandée, `sim_genere.cle_complete` est comparée à
  `plan_langage.cle_complete`. Un seul écart → arrêt. Puis nœuds et états comparés à la référence.
- `mesure` : passes alternées référence / G, temps CPU du processus, mêmes nœuds et états exigés.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/controle_g50t.py controle|mesure [jeu niveau noeuds passes]"""
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "experiments/T3.0"))
os.chdir(RACINE / "experiments/T3.0")
import plafonds

import chrysalide.arc3.sim_rapide as sr
from chrysalide.arc3 import sim_genere as g
from chrysalide.arc3.logique import plan_langage as pl

ORIG_CLONER, ORIG_CLE = sr.cloner, pl.cle_complete
N = {"copies": 0, "cles": 0, "coups": 0}


def cloner_controle(sc, etat):
    a = ORIG_CLONER(sc, etat)
    b = g.cloner(sc, etat)
    if ORIG_CLE(*a) != ORIG_CLE(*b):
        raise AssertionError(f"copie différente (copie n° {N['copies']})")
    N["copies"] += 1
    return b


def cle_controle(sc, etat):
    k = ORIG_CLE(sc, etat)
    if g.cle_complete(sc, etat) != k:
        raise AssertionError(f"clé différente (clé n° {N['cles']})")
    N["cles"] += 1
    return k


ORIG_PROG = sr.ProgrammeCompile


class Verifie(g.ProgrammeGenere):
    """Chaque coup est aussi joué par `ProgrammeCompile` sur une copie : même issue, même exception, même clé, même image."""

    def __init__(self, texte):
        super().__init__(texte)
        self.ref = ORIG_PROG(texte)

    def step(self, scene, action, niveau=0):
        sc_r, et_r = ORIG_CLONER(scene, self.etat)
        self.ref.etat = et_r
        err_r = err = None
        try:
            self.ref.step(sc_r, action, niveau)
        except Exception as e:  # noqa: BLE001
            err_r = type(e)
        try:
            super().step(scene, action, niveau)
        except Exception as e:  # noqa: BLE001
            err = type(e)
        if err != err_r:
            raise AssertionError(f"exception différente au coup n° {N['coups']} : {err_r} contre {err}")
        if err is None and (ORIG_CLE(sc_r, self.ref.etat) != ORIG_CLE(scene, self.etat)
                            or not (sr.image(sc_r) == sr.image(scene)).all() or sc_r.issue != scene.issue):
            raise AssertionError(f"coup n° {N['coups']} différent")
        N["coups"] += 1
        if err is not None:
            raise RuntimeError("règle qui plante, comme la référence")


def passe(jeu, niveau, noeuds, mode):
    """mode : ref | G1 (copie + clé) | G (copie + clé + règles générées) | controle (G, vérifié à chaque nœud)."""
    sr.cloner, plafonds.cle_complete = {"ref": (ORIG_CLONER, ORIG_CLE), "G1": (g.cloner, g.cle_complete),
                                        "G": (g.cloner, g.cle_complete),
                                        "controle": (cloner_controle, cle_controle)}[mode]
    sr.ProgrammeCompile = {"G": g.ProgrammeGenere, "controle": Verifie}.get(mode, ORIG_PROG)
    try:
        t = time.process_time()
        r = plafonds.p0(jeu, niveau, noeuds, 3600, "but")
        return r, time.process_time() - t
    finally:
        sr.cloner, plafonds.cle_complete, sr.ProgrammeCompile = ORIG_CLONER, ORIG_CLE, ORIG_PROG


def main():
    quoi = sys.argv[1]
    jeu, niveau, noeuds = (sys.argv[2], int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else ("g50t", 1, 20000)
    if quoi == "controle":
        ref, _ = passe(jeu, niveau, noeuds, "ref")
        r, _ = passe(jeu, niveau, noeuds, "controle")
        ok = (r["noeuds"], r["etats"], r["plan"]) == (ref["noeuds"], ref["etats"], ref["plan"])
        print(json.dumps({"jeu": jeu, "niveau": niveau, **N, "ref": [ref["noeuds"], ref["etats"], ref["plan"]],
                          "G": [r["noeuds"], r["etats"], r["plan"]], "identique": ok}))
        return
    passes = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    out = {"ref": [], "G1": [], "G": []}
    for _ in range(passes):
        for mode in ("ref", "G1", "G"):
            r, dt = passe(jeu, niveau, noeuds, mode)
            out[mode].append({"noeuds": r["noeuds"], "etats": r["etats"], "cpu": round(dt, 2),
                              "n_par_s": round(r["noeuds"] / dt)})
    meilleur = {m: max(x["n_par_s"] for x in v) for m, v in out.items()}
    print(json.dumps({"jeu": jeu, "niveau": niveau, **out, "gain_G1": round(meilleur["G1"] / meilleur["ref"], 2), "gain": round(meilleur["G"] / meilleur["ref"], 2)}))


if __name__ == "__main__":
    main()
