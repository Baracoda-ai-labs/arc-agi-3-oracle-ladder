# SPDX-License-Identifier: MIT-0
"""F (autopsie, CW-468.1) : classe chaque échec de `autopsie.py` à sa 1ʳᵉ divergence, à partir de l'image réelle et des
cases fausses. DIAGNOSTIC SEULEMENT : la vérité T4 (`verite.json`, bordure, panneau) sert à nommer ce qui bloque ; elle
n'entre dans aucune correction.
  - réel : le coup n'a rien changé (≤ 8 px, la jauge) → « déplacement prédit, bloqué en réalité » ; on dit si les cases
    où le simulateur met l'objet sont HORS du terrain (bordure ou panneau) ;
  - réel : l'objet a bougé, mais pas de victoire alors que le simulateur dit « niveau » → « but supposé faux ».
Usage : uv run python experiments/oracle/autopsie_classer.py <autopsie.json> <run> → tableau + <autopsie>_classe.json"""
import collections
import glob
import json
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
VER = {f.split("/")[-3].lower(): json.loads(Path(f).read_text())
       for f in glob.glob(str(R / "experiments/T4/jeux/t4/environment_files/*/*/verite.json"))}


def hors_terrain(g, n, cases):
    els = VER[g]["niveaux"][n - 1]["elements"] if g in VER else []
    bord = next((e for e in els if e["type"] == "bordure"), None)
    if not bord or not cases:
        return None
    bx, by, bw, bh = bord["bbox"]
    return any(not (bx < x < bx + bw - 1 and by < y < by + bh - 1) for y, x, *_ in cases)


def classer(k, v, run):
    g, n, c = k.split(":")
    n, c = int(n), int(c)
    if v.get("etat") == "victoire":
        return "victoire (contrôle positif)", None
    if v.get("etat") not in ("divergence", "mort"):
        return "autre : " + str(v.get("etat")), None
    ims = np.load(Path(run) / g / f"N{n}" / "partie.npz")["images"]
    p = v["pas"]
    d = int((ims[c + p - 1] != ims[c + p]).sum())
    h = hors_terrain(g, n, v.get("cases"))
    if d <= 8:
        cl = "déplacement prédit, BLOQUÉ en réalité"
        return cl + (" — hors du terrain (bord jamais heurté)" if h else " — dans le terrain"), h
    if v.get("issue_simulee") == "niveau":
        return "objet déplacé, but supposé atteint, PAS de victoire (but faux)", h
    return "changement réel non prédit", h


def main():
    src, run = Path(sys.argv[1]), sys.argv[2]
    d = json.loads(src.read_text())
    c = collections.Counter()
    ex = collections.defaultdict(list)
    for k, v in d.items():
        cl, _ = classer(k, v, run)
        v["classe"] = cl
        c[cl] += 1
        ex[cl].append(k)
    for cl, n in c.most_common():
        print(f"{n:3d}  {cl}   ex. {ex[cl][:4]}")
    src.with_name(src.stem + "_classe.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
