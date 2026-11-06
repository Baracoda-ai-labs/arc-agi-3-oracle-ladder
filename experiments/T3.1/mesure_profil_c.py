# SPDX-License-Identifier: MIT-0
"""CW-111 : part des règles de chaque regles/<jeu>.json qui tient dans le profil C (induisible par l'ASP), et raisons
les plus fréquentes hors profil. Usage : uv run python experiments/T3.1/mesure_profil_c.py"""
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from chrysalide.arc3.profil_c import bilan

D = pathlib.Path(__file__).parent
ref = json.loads((D / "nonreg_ref.json").read_text()) if (D / "nonreg_ref.json").exists() else {}
raisons, tot_in, tot = collections.Counter(), 0, 0
print("jeu    dans/total  honnête")
for f in sorted((D / "regles").glob("*.json")):
    n_in, n, hors = bilan(json.loads(f.read_text()))
    tot_in, tot = tot_in + n_in, tot + n
    h = ref.get(f.stem, {}).get("reproduit", "?") if isinstance(ref.get(f.stem), dict) else "?"
    print(f"{f.stem:6} {n_in:3}/{n:<3}      {h}")
    for rs in hors.values():
        raisons.update({x.split(" :")[0] for x in rs})
print(f"TOTAL {tot_in}/{tot} règles dans le profil C ({100 * tot_in / max(tot, 1):.0f} %)")
for x, k in raisons.most_common(8):
    print(f"  {k:4} × {x}")
