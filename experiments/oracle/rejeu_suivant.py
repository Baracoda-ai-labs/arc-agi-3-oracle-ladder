# SPDX-License-Identifier: MIT-0
"""F (CW-449, report d'un niveau à l'autre) : correctif le moins cher, mesuré hors ligne. Au début du niveau k + 1,
rejouer tel quel le plan qui a gagné le niveau k (plan P0 de `plans/`) : gagne-t-il le niveau k + 1 ? Le jeu est amené
au niveau k + 1 par le préfixe enregistré. → experiments/oracle/rejeu_suivant.json"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
import plafonds

from chrysalide.arc3.logique.jeux import jouer_action

res = {}
for f in sorted((Path(__file__).parent / "plans").glob("*_N*.json")):
    d = json.loads(f.read_text())
    g, k, plan = d["jeu"], d["niveau"], d.get("plan_p1")
    if not plan:
        continue
    env, fr = plafonds.env_au_niveau(g, k + 1)
    if env is None:
        res[f"{g}:{k + 1}"] = {"mesure": False, "raison": "pas de préfixe vers le niveau suivant"}
        continue
    base, joues, issue = fr.levels_completed, 0, "rien"
    for a in plan:
        fr = jouer_action(env, tuple(a) if isinstance(a, list) else a)
        joues += 1
        if fr.levels_completed > base:
            issue = "gagné"
            break
        if "GAME_OVER" in str(fr.state):
            issue = "mort"
            break
    res[f"{g}:{k + 1}"] = {"mesure": True, "plan_du_niveau": k, "longueur": len(plan), "joues": joues, "issue": issue}
    print(g, k + 1, res[f"{g}:{k + 1}"], flush=True)
(Path(__file__).parent / "rejeu_suivant.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
print("gagnés :", sum(v.get("issue") == "gagné" for v in res.values()), "/", sum(v.get("mesure") for v in res.values()))
