# SPDX-License-Identifier: MIT-0
"""F (substitution d'oracle DANS P1, volet plan) : plan P0 vérifié dans le vrai jeu (règles et but exacts, `but` puis
`paliers`, 1 M nœuds / 600 s) pour un niveau, enregistré coup par coup au format de P1 (1-5, ou ("clic", x, y) en pixels).
Usage : uv run python experiments/oracle/plans_p0.py <jeu> <k> → experiments/oracle/plans/<jeu>_N<k>.json"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(RACINE / "experiments/instrument"), str(RACINE / "experiments/T3.0"),
                str(RACINE / "experiments/T3.1")]
import diag4
import oracle_niveau

gid, k = sys.argv[1], int(sys.argv[2])
plan, rech, r = (diag4.plan_D if k == 1 else oracle_niveau.plan_D_k(k))(gid)
p1 = None if plan is None else [["clic", int(c[2]), int(c[1])] if c[0] == 6 else int(c[0]) for c in plan]
(Path(__file__).parent / "plans" / f"{gid}_N{k}.json").write_text(json.dumps(
    {"jeu": gid, "niveau": k, "recherche": rech, "plan_p0": plan, "plan_p1": p1, "raison": r.get("raison")}, default=str))
print(gid, k, rech, None if p1 is None else len(p1), r.get("raison"), flush=True)
