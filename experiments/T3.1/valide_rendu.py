"""CW-089 : valide le noyau de rendu de l'interpréteur (ontologie_exec.rendre) contre le vrai rendu du moteur, HUD retiré,
image par image sur les traces de R0 rejouées (25 jeux). Usage : uv run python experiments/T3.1/valide_rendu.py"""
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "experiments/T2.12"))
from arc_agi import Arcade, OperationMode
from arcengine.enums import GameAction
from fidelite import NUM, evenements

from chrysalide.arc3.ontologie_exec import rendre, scene_moteur

arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(RACINE / "experiments/arc3/environment_files"))
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}  # docs/TEMOINS.md : on ne rejoue plus leurs traces (CW-088)
tot = ok = 0
for f in sorted((RACINE / "runs_pod/R0").glob("*/artifacts/*_events.jsonl")):
    if Path(f).name[:4] in TEMOINS:
        continue
    env = arc.make(Path(f).name.split("_p")[0])
    env.reset()
    n = e_ok = 0
    for e in evenements(f):
        if "board" not in e:
            continue
        if e.get("type") != "initial":
            nom = e.get("action_name", "")
            if nom not in NUM:
                continue
            a = GameAction.from_id(NUM[nom])
            if NUM[nom] == 6:
                aff = e["action_display"]
                r, c = (int(x.split("=")[1]) for x in aff[aff.index("(") + 1:-1].split(", "))
                env.step(a, data={"x": c, "y": r})
            else:
                env.step(a)
        scene, vrai = scene_moteur(env)
        n += 1
        e_ok += bool(np.array_equal(rendre(scene), vrai))
    tot += n
    ok += e_ok
    print(f"{Path(f).name[:4]} {e_ok}/{n}", flush=True)
print(f"TOTAL rendu exact (HUD exclu) : {ok}/{tot}")
