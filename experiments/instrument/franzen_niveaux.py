# SPDX-License-Identifier: MIT-0
"""CW-252 : niveaux gagnés par Franzen, et en combien de coups, d'après les artefacts d'un passage déjà fait (aucun calcul).
Coups d'un niveau = actions jouées depuis la fin du niveau précédent (morts et relances comprises).
Usage : python experiments/instrument/franzen_niveaux.py <dossier_artifacts> → JSON {jeu: {niveau: coups}} sur la sortie"""
import json
import sys
from pathlib import Path

TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


def niveaux(f):
    out, debut, n = {}, 0, 0
    for ligne in f.read_text().splitlines():
        e = json.loads(ligne)
        if e.get("type") != "action":
            continue
        n += 1
        if e.get("level_completed"):
            out[int(e.get("level", 1)) - 1 or len(out) + 1] = n - debut
            debut = n
    return out


if __name__ == "__main__":
    res = {}
    for f in sorted(Path(sys.argv[1]).glob("*_events.jsonl")):
        g = f.name.split("-")[0]
        if g not in TEMOINS:
            res[g] = niveaux(f)
    print(json.dumps(res))
