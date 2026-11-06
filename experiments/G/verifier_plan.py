"""[G] CW-369 (prototype « un langage logique qui apprend, vérifie et joue ») : VÉRIFICATION COMMUNE d'un plan, quelle
que soit la méthode qui l'a trouvé (noyau ASP de C, macro_g, sous-buts). Deux étages, arrêt à la 1re divergence :
  1. programme exporté du dossier de C (but du dossier ou `--but`) : issue « niveau » atteinte ? à quel coup ?
  2. vrai jeu (préfixe `plafonds.env_au_niveau`, jeu public) : niveau franchi ? à quel coup ?
Coups : noms (UP, DOWN, LEFT, RIGHT, SPACE) et clics `CLICK(y, x)` (case du langage = pixel, échelle 1 ; sinon donner
`--echelle s,ox,oy`). Usage : PYTHONPATH=. .venv/bin/python experiments/G/verifier_plan.py <dossier> "<c1,c2,…>"
       [--but "<tuple>"] [--echelle s,ox,oy] → une ligne JSON"""
import argparse
import json
import os
import pickle
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
CODE = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5}


def lire_coups(texte):
    return [c.strip() for c in re.findall(r"CLICK\([^)]*\)|[A-Z]+", texte)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier")
    ap.add_argument("plan")
    ap.add_argument("--but")
    ap.add_argument("--echelle", default="1,0,0")
    a = ap.parse_args()
    chemin = Path(a.dossier) if Path(a.dossier).exists() else R / f"experiments/T3.0/dossiers_g/{a.dossier}.pkl"
    D = pickle.loads(chemin.read_bytes())
    os.environ.update(D.get("drapeaux", {}))
    sys.path += [str(R / "experiments/T3.0"), str(R / "experiments/T3.1")]
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.ontologie_exec import Scene
    from chrysalide.arc3.sim_rapide import ProgrammeCompile
    th = D["theorie"]
    if a.but:
        th.but = eval(a.but)
    elif getattr(th, "but", None) is None:
        th.but = D["buts"][0]
    coups = lire_coups(a.plan)
    s_, ox, oy = (int(v) for v in a.echelle.split(","))
    prog, non = exporter(th, D["taille"])
    p = ProgrammeCompile(prog)
    s = Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])
    prog_ok = None
    for i, c in enumerate(coups, 1):
        m = re.findall(r"\d+", c)
        p.step(s, ("CLICK", int(m[0]), int(m[1])) if c.startswith("CLICK") else (c, None, None))
        if s.issue is not None:
            prog_ok = (s.issue, i)
            break
    os.chdir(R)
    import plafonds as pf
    env, f0 = pf.env_au_niveau(D["jeu"], D["niveau"])
    f, joues = f0, 0
    for c in coups:
        m = re.findall(r"\d+", c)
        coup = (6, int(m[0]) * s_ + oy, int(m[1]) * s_ + ox) if c.startswith("CLICK") else (CODE[c], None, None)
        f = pf.jouer(env, coup)
        joues += 1
        if f.levels_completed > f0.levels_completed or f.state.name in ("WIN", "GAME_OVER"):
            break
    print(json.dumps({"dossier": chemin.stem, "but": str(th.but)[:120], "non_exportes": non, "coups": len(coups),
                      "programme": {"issue": prog_ok[0] if prog_ok else None, "au_coup": prog_ok[1] if prog_ok else None},
                      "vrai_jeu": {"franchi": f.levels_completed > f0.levels_completed or f.state.name == "WIN",
                                   "etat": f.state.name, "joues": joues}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
