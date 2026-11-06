# SPDX-License-Identifier: MIT-0
"""Décomposition du temps des requêtes au serveur (CW-224.2) : lit les lignes ReqTimeStats de SGLang dans serve.log, sur une
fenêtre horaire (UTC du pod). Par fenêtre : requêtes, jetons d'entrée (dont en cache), de sortie, durées attente / préremplissage /
génération (somme et p50/p95), débit de génération par requête.
Usage (pod) : python3 scripts/pod/temps_tour.py /workspace/runs/serve.log "nom:AAAA-MM-JJ HH:MM:AAAA-MM-JJ HH:MM" …"""
import re
import sys
from datetime import datetime

RX = re.compile(r"^\[(\S+ \S+)\] ReqTimeStats\(.*?input_len=(\d+), cached_input_len=(\d+), output_len=(\d+).*?\): "
                r"queue_duration=([\d.]+)ms, initial_prefill_elapsed=([\d.]+)ms, post_prefill_elapsed=([\d.]+)ms")


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def main(log, *fenetres):
    fs = []
    for f in fenetres:
        nom, a, b = f.split("|")
        fs.append((nom, datetime.fromisoformat(a), datetime.fromisoformat(b), []))
    with open(log, errors="ignore") as fh:
        for ligne in fh:
            m = RX.match(ligne)
            if not m:
                continue
            t = datetime.fromisoformat(m.group(1))
            for nom, a, b, acc in fs:
                if a <= t < b:
                    acc.append(tuple(float(x) for x in m.groups()[1:]))
    print("bloc | req | entrée moy | cache % | sortie moy | attente p50/p95 s | préremplissage p50/p95 s | génération p50/p95 s | jetons/s génération p50 | s de génération totales")
    for nom, a, b, acc in fs:
        if not acc:
            print(nom, "aucune requête")
            continue
        n = len(acc)
        inp = sum(x[0] for x in acc) / n
        cache = 100 * sum(x[1] for x in acc) / max(1, sum(x[0] for x in acc))
        out = sum(x[2] for x in acc) / n
        att, pre, gen = [x[3] / 1e3 for x in acc], [x[4] / 1e3 for x in acc], [x[5] / 1e3 for x in acc]
        vit = [x[2] / (x[5] / 1e3) for x in acc if x[5] > 0]
        print(f"{nom} | {n} | {inp:.0f} | {cache:.0f} | {out:.0f} | {q(att, .5):.2f}/{q(att, .95):.2f} | "
              f"{q(pre, .5):.2f}/{q(pre, .95):.2f} | {q(gen, .5):.1f}/{q(gen, .95):.1f} | {q(vit, .5):.0f} | {sum(gen):.0f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
