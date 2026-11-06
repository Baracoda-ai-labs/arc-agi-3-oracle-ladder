# SPDX-License-Identifier: MIT-0
"""F (CW-448, classe S, correctif 1) : recherches par nouveauté IW(1) puis IW(2) (déjà dans `plafonds.p0`), bras « tout
exact », 1 M nœuds / 600 s chacune, sur un niveau S. Le plan trouvé est rejoué dans le VRAI jeu (`verifier_plan`).
Usage : uv run python experiments/oracle/iw_s.py <jeu> <k> <sortie.json>"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
import plafonds

gid, k, sortie = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
res = {}
for rech in ("iw1", "iw2"):
    r = plafonds.p0(gid, k, 1000000, 600, rech)
    res[rech] = {x: r.get(x) for x in ("gagne", "raison", "plan", "noeuds", "etats", "secondes")}
    print(gid, k, rech, res[rech], flush=True)
    sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    if r.get("gagne"):
        break
