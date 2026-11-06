"""[G] CCM-048-G : A* guidé par le but (`astar_but.py`) contre macro_g, à temps égal, sur le dossier de C ka59 N4
(`ka59_n4_creux.pkl`, but du dossier) et sur g50t N1 (théorie déf. 2, départ après 5 coups, contrôle) ; plan ka59 →
`verifier_plan.py`. Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_astar.py <ka59|g50t> [secondes=60] [poids=3]"""
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(R / "experiments/G")]
cas, sec = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 60
poids = float(sys.argv[3]) if len(sys.argv) > 3 else 3
if cas == "ka59":
    D = pickle.loads((R / "experiments/T3.0/dossiers_g/ka59_n4_creux.pkl").read_bytes())
    os.environ.update(D["drapeaux"])
else:
    for f in ("CHRYS_RETOUR", "CHRYS_FANTOME", "CHRYS_POURSUITE_UTILE", "CHRYS_TENUE", "CHRYS_TRAITS_FINS", "CHRYS_BUT_CENTRE"):
        os.environ[f] = "1"
    os.environ["CHRYS_AMODAL"] = "2"
from astar_but import _rendu, astar, h_but

from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile

if cas == "ka59":
    th = D["theorie"]
    th.but = next(b for b in D["buts"] if b[0] == "emboite")
    if os.environ.get("G_BUT"):  # variante de but pour diagnostic, annoncée au rapport
        th.but = eval(os.environ["G_BUT"])  # noqa: S307
    prog, _ = exporter(th, D["taille"])
    s = Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])
    etat = ProgrammeCompile(prog).etat
    fl, clics = ("UP", "DOWN", "LEFT", "RIGHT"), {_rendu(c) for c in th.but[2]}
else:
    d = pickle.loads((R / "experiments/T3.0/g50t_def2/theorie_victoire.pkl").read_bytes())
    th = d["th2"]
    th.but = ("centre", 281, 9)
    prog, _ = exporter(th, d["taille"])
    s = Scene((d["taille"][1], d["taille"][0]), d["fond"], d["fond"], [_sprite(o) for o in d["tr2_0"]])
    p = ProgrammeCompile(prog)
    for a in d["joues"]:
        p.step(s, (a, None, None))
    etat = p.etat
    fl, clics = ("UP", "DOWN", "LEFT", "RIGHT", "SPACE"), None
plan, inf = astar(prog, s, etat, h_but(th.but), fl, clics, poids, sec)
ligne = {"cas": cas, "but": str(th.but)[:100], "poids": poids, "plan": None if plan is None else len(plan), **inf,
         "coups": plan}
if plan and cas == "ka59":
    r = subprocess.run([sys.executable, str(R / "experiments/G/verifier_plan.py"), "ka59_n4_creux", ",".join(plan), "--but", str(th.but)],
                       capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(R)}, check=False)
    ligne["verification"] = json.loads([x for x in r.stdout.splitlines() if x.startswith("{")][-1])
print(json.dumps(ligne, ensure_ascii=False))
