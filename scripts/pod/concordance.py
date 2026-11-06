#!/usr/bin/env python3
"""Contrôles 1 et 2 de l'amendement A, jugés sur les sorties rapatriées du pod. Seuils fixés AVANT le pod :
concordance |Δ exactitude| <= 8 points par condition, et chaque famille du pod dans l'IC de Wilson 95 % du Mac ;
F-C2 : boucle sans outil = oracle direct, caractère pour caractère. Usage : scripts/pod/concordance.py <run pod>"""
import json
import sys
from pathlib import Path

from scripts.e0_mutate import wilson

REF = {  # passe pod -> sorties du Mac (4 bits) sur les mêmes tâches
    "conc_t06_oracle_p": "experiments/20260927_T0.8/raw/e1_s1_oracle_p.jsonl",
    "conc_t08_oracle_np": "experiments/20260927_T0.8/raw/e1_s1_oracle_np.jsonl",
    "conc_t08_bm25_np": "experiments/20260927_T0.8/raw/e1_s1_bm25_np.jsonl",
}


def lire(p):
    return {r["task"]: r for r in map(json.loads, Path(p).open())}


def main(run):
    raw, ok = Path(run) / "raw", True
    for passe, ref in REF.items():
        pod, mac = lire(raw / f"{passe}.jsonl"), lire(ref)
        com = sorted(pod.keys() & mac.keys())
        def acc(d, com=com):
            return sum(d[t]["status"] == "correct" for t in com) / len(com)
        delta = 100 * (acc(pod) - acc(mac))
        fams = {}
        for f in "ABC":
            ts = [t for t in com if mac[t]["family"] == f]
            km, kp = sum(mac[t]["status"] == "correct" for t in ts), sum(pod[t]["status"] == "correct" for t in ts)
            lo, hi = wilson(km, len(ts))
            fams[f] = lo <= kp / len(ts) <= hi
        verdict = abs(delta) <= 8 and all(fams.values())
        ok &= verdict
        print(f"{passe} : n = {len(com)}, Mac {acc(mac):.0%}, pod {acc(pod):.0%}, Δ = {delta:+.1f} pts, familles dans le Wilson du Mac "
              f"{fams} -> {'OK' if verdict else 'ÉCHEC'}")
    a, b = lire(raw / "fc2_oracle_boucle_np.jsonl"), lire(raw / "conc_t08_oracle_np.jsonl")
    same = sum(a[t]["output"] == b[t]["output"] for t in a)
    ok &= same == len(a)
    print(f"F-C2 boucle sans outil = oracle direct : {same}/{len(a)} identiques -> {'OK' if same == len(a) else 'ÉCHEC'}")
    print("CONTRÔLES 1-2 :", "OK" if ok else "ÉCHEC : arrêt, lecture des sorties avant toute autre étape")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1]) else 1)
