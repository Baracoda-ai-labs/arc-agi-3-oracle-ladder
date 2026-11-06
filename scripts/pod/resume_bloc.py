# SPDX-License-Identifier: MIT-0
"""Résumé en 5 lignes d'un bloc (CW-047) : RHAE total, niveaux, actions, tours/h, GPU moyen. Lit, dans /workspace/runs/<bloc>/ :
summary.txt du harnais, util.csv (mesure_cpu.sh), artifacts/*_events.jsonl. Tour = étape d'analyse du harnais (analysis_step
distincts, même règle que analyse_appariee.py de B ; arbitrage CW-048) ; colonne secondaire : requêtes au modèle (*_requests.jsonl[.gz]).
Usage (sur le pod) : python3 scripts/pod/resume_bloc.py /workspace/runs/<bloc>"""
import glob
import gzip
import json
import re
import sys
from pathlib import Path


def resume(d):
    d = Path(d)
    summ = sorted(d.glob("*/summary.txt"))
    s = summ[-1].read_text() if summ else ""
    moy = re.search(r"mean score:\s+([\d.]+)", s)
    debut, fin = re.search(r"started:\s+(.+)", s), re.search(r"ended:\s+(.+)", s)
    niv = [(float(a), int(b)) for a, b in re.findall(r"levels=([\d.]+)/(\d+)", s)]
    act = sum(int(x) for x in re.findall(r"actions=(\d+)", s))
    tours = 0
    for f in sorted(d.glob("**/artifacts/*_events.jsonl")):
        etapes = set()
        for ligne in f.read_text().splitlines():
            e = json.loads(ligne)
            if e.get("type") == "analysis" or (e.get("type") == "action" and e.get("action_name") != "RESET"):
                etapes.add(e.get("analysis_step"))
        tours += len(etapes)
    requetes = 0
    for f in glob.glob(str(d / "*" / "*_requests.jsonl*")):
        op = gzip.open if f.endswith(".gz") else open
        with op(f, "rt") as h:
            requetes += sum('"event": "request"' in ligne for ligne in h)
    u = [ligne.split("\t") for ligne in (d / "util.csv").read_text().splitlines()[2:]] if (d / "util.csv").exists() else []
    gpu = [float(x[2]) for x in u if len(x) > 2 and x[2]]
    duree_h = (int(u[-1][0]) - int(u[0][0])) / 3600 if len(u) > 1 else 0
    lignes = [
        f"{d.name} : RHAE moyen {moy.group(1) if moy else '?'} sur {len(niv)} jeux ({debut.group(1) if debut else '?'} → {fin.group(1) if fin else '?'})",
        f"niveaux {sum(a for a, _ in niv):.0f} / {sum(b for _, b in niv)} ; jeux avec ≥ 1 niveau : {sum(a > 0 for a, _ in niv)}",
        f"actions {act}",
        (f"tours (étapes d'analyse) {tours} ; {tours / duree_h:.0f} tours/h sur {duree_h:.2f} h ; requêtes au modèle {requetes} "
         f"({requetes / duree_h:.0f}/h)") if duree_h else f"tours {tours} ; requêtes {requetes}",
        f"GPU moyen {sum(gpu) / len(gpu):.0f} % (min {min(gpu):.0f}) sur {len(gpu)} mesures" if gpu else "GPU : pas de mesure",
    ]
    return "\n".join(lignes)


if __name__ == "__main__":
    print(resume(sys.argv[1]))
