# SPDX-License-Identifier: MIT-0
"""Résumé d'un essai bout en bout (E2E*) : par jeu, issue du harnais (niveaux, score, actions) + activité du moteur lue
dans les traces de la branche (appels, portes, porte faible, coups joués avec / sans effet, déclencheurs, CPU).
Usage : python scripts/pod/resume_e2e.py runs_pod/E2E4_A [runs_pod/E2E4_ls20_g1 …]"""
import collections
import json
import re
import sys
from pathlib import Path


def harnais(run):
    out = {}
    for ligne in (run / "run.log").read_text(errors="replace").splitlines():
        m = re.search(r"\[finished\] (\w{4})-\S+ state=(\w+) level=(\d+)/(\d+) score=([\d.]+) actions=(\d+)", ligne)
        if m:
            out[m[1]] = {"etat": m[2], "niveaux": f"{m[3]}/{m[4]}", "score": float(m[5]), "actions": int(m[6])}
    return out


def traces(run):
    out = {}
    for f in sorted((run / "chrysalide").glob("*_trace.jsonl")):
        c = collections.Counter()
        dec, cpu = collections.Counter(), 0.0
        for ligne in f.read_text(errors="replace").splitlines():
            try:
                r = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            src = r.get("source")
            if src == "moteur" and r.get("appel"):
                c["appels"] += 1
                cpu += float(r.get("cpu_s") or 0)
                c["porte1"] += bool(r.get("porte"))
                c["faible_ok"] += bool(r.get("porte_faible") and r.get("porte1_c") and r.get("porte2_c"))
            elif src == "moteur" and "lot" in r and not r.get("divergence"):
                c["coups_effet" if r.get("sans_effet") is False else "coups_sans_effet"] += 1
            elif src == "moteur" and r.get("divergence"):
                c["divergences"] += 1
            elif src == "modele":
                c["tours_llm"] += 1
                dec[r.get("declencheur")] += 1
            elif src == "tuto" and "lot" in r:
                c["coups_tuto"] += 1
        out[f.name[:4]] = {**c, "cpu_moteur_s": round(cpu, 1), "declencheurs": dict(dec.most_common(3))}
    return out


if __name__ == "__main__":
    for d in sys.argv[1:]:
        run = Path(d)
        h, t = harnais(run), traces(run)
        print(f"== {run.name}")
        for jeu in sorted(set(h) | set(t)):
            print(jeu, json.dumps({**h.get(jeu, {}), **t.get(jeu, {})}, ensure_ascii=False))
