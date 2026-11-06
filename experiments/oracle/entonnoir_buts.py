# SPDX-License-Identifier: MIT-0
"""F (CW-458, chantier 2 « plus de buts », appui de D) : précondition sur les journaux T1b (`T1_releve_p1/runs/joue2_*`).
Occasions « théorie sans but », par famille de but VRAIE (T4 : `verite.json`, dédale = aller à la sortie, tuiles =
reproduire le motif) ; buts proposés et leur issue ; niveaux gagnés par famille.
Usage : uv run python experiments/oracle/entonnoir_buts.py"""
import collections
import glob
import json
from pathlib import Path

V = "experiments/T4/jeux/t4/environment_files/*/*/verite.json"
FAM = {f.split("/")[-3].lower(): json.loads(Path(f).read_text())["famille"] for f in glob.glob(V)}
NB = {f.split("/")[-3].lower(): len(json.loads(Path(f).read_text())["niveaux"]) for f in glob.glob(V)}

for run in ("joue2_t4_g0", "joue2_t4_g1"):
    sans, buts, issues, niv = (collections.Counter() for _ in range(4))
    for f in glob.glob(f"experiments/T1_releve_p1/runs/{run}/*/journal_jeu.jsonl"):
        g = f.split("/")[-2].lower()
        F, occ, but = FAM.get(g, "?"), {}, {}
        for ligne in Path(f).read_text().splitlines():
            e = json.loads(ligne)
            if e.get("type") != "moteur":
                continue
            k = (e["niveau"], e["coup"])
            occ.setdefault(k, set()).add(e["etape"])
            if e["etape"] == "but":
                but[k] = e["but"].split(",")[0].strip("('\" ")
                buts[(F, but[k])] += 1
            if e["etape"] == "resultat":
                issues[(F, but.get(k), e["issue"])] += 1
        sans[F] += sum(1 for s in occ.values() if "theorie" in s and "but" not in s)
        r = json.loads(Path(f.replace("journal_jeu.jsonl", "resultat.json")).read_text())
        niv[(F, "gagnés")] += sum(x["victoire"] for x in r)
        niv[(F, "niveaux")] += NB.get(g, 0)
    print(run, "| théorie sans but :", dict(sans), "| buts :", dict(buts))
    print("   issues :", dict(issues), "| niveaux :", dict(niv))
