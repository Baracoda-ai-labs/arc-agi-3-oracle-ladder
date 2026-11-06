"""[G] Rejoue un plan (noms d'action) dans le VRAI jeu re86 au début du niveau k (préfixe de `plafonds.env_au_niveau`),
coup par coup ; → niveau franchi ou non, coups joués, état final. Usage : rejeu_re86.py <k> <UP,DOWN,…> [jeu=re86]"""
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
os.chdir(RACINE)
import plafonds as pf  # noqa: E402

CODE = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5}
k, plan = int(sys.argv[1]), sys.argv[2].split(",")
gid = sys.argv[3] if len(sys.argv) > 3 else "re86"
env, f0 = pf.env_au_niveau(gid, k)
n0 = f0.levels_completed
f, joues = f0, 0
for a in plan:
    f = pf.jouer(env, (CODE[a], None, None))
    joues += 1
    if f.levels_completed > n0 or f.state.name in ("WIN", "GAME_OVER"):
        break
print(json.dumps({"jeu": gid, "niveau": k, "niveaux_avant": n0, "niveaux_apres": f.levels_completed, "coups": joues,
                  "sur": len(plan), "etat": f.state.name, "franchi": f.levels_completed > n0 or f.state.name == "WIN"}))
