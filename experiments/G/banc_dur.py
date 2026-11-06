"""[G] CW-373.4 : `macro_g` au banc à BUDGET MURAL DUR (comme `banc_noyau_asp.py` d'Astra : démarrage et chargement
compris, processus tué à la limite), sur les mêmes cas que le noyau ASP de C :
  g50t N1 : théorie `g50t_def2/theorie_victoire.pkl`, départ après les 5 coups d'exploration, but centre(281, 9) ;
  ka59 N4 : dossier `ka59_n4_creux.pkl` (but `emboite` du dossier, clics recalculés sur la scène, pilotés seulement),
            macro_g seul et sous-buts cumulés.
Plan rendu → `verifier_plan.py` (ka59) pour programme + vrai jeu. Usage : banc_dur.py [secondes=30] → lignes JSON"""
import json
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
PY = str(R / ".venv/bin/python")
G50T = r'''
import os, sys, pickle, json
sys.path[:0] = ["experiments/G", "experiments/T3.0", "experiments/T3.1"]
for f in ("CHRYS_RETOUR","CHRYS_FANTOME","CHRYS_POURSUITE_UTILE","CHRYS_TENUE","CHRYS_TRAITS_FINS","CHRYS_BUT_CENTRE"):
    os.environ[f] = "1"
os.environ["CHRYS_AMODAL"] = "2"
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile
d = pickle.loads(open("experiments/T3.0/g50t_def2/theorie_victoire.pkl", "rb").read())
th = d["th2"]; th.but = ("centre", 281, 9)
prog, _ = exporter(th, d["taille"])
s = Scene((d["taille"][1], d["taille"][0]), d["fond"], d["fond"], [_sprite(o) for o in d["tr2_0"]])
p = ProgrammeCompile(prog)
for a in d["joues"]:
    p.step(s, (a, None, None))
from banc_p0 import _init
_init(); import macro_g
r = macro_g.chercher("g50t", 1, 10**6, SEC, texte=prog, scene=s, etat=p.etat, actions=[1, 2, 3, 4, 5], verifier=False)
print("RESULTAT", json.dumps({x: r.get(x) for x in ("arret", "plan", "etats_hauts", "coups", "cpu")}))
'''


def lancer(nom, cmd, sec, env=None):
    import os
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=R, capture_output=True, text=True, timeout=sec,
                           env={**os.environ, "PYTHONPATH": str(R), **(env or {})}, check=False)
        lignes = [x for x in r.stdout.splitlines() if x.startswith(("RESULTAT", "{"))]
        res = {"statut": "FINI", "sortie": lignes[-3:]}
    except subprocess.TimeoutExpired:
        res = {"statut": "TEMPS_DUR"}
    res |= {"cas": nom, "budget": sec, "mur": round(time.monotonic() - t0, 1)}
    print(json.dumps(res, ensure_ascii=False), flush=True)
    return res


def main():
    sec = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    marge = max(1.0, sec * 0.15)  # le budget de recherche laisse la place au chargement, le mur reste dur
    lancer("g50t_n1 macro_g", [PY, "-c", G50T.replace("SEC", str(sec - marge))], sec)
    k = str(R / "experiments/G/banc_ka59.py")
    lancer("ka59_n4 macro_g", [PY, k, str(sec - marge)], sec, {"G_CLICS_SCENE": "1"})
    lancer("ka59_n4 sous-buts", [PY, k, str(sec - marge)], sec, {"G_SOUSBUTS": "1", "G_T_ESSAI": str((sec - marge) / 2)})


if __name__ == "__main__":
    main()
