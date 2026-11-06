"""[G] CW-357 (liste d'`Experience`, source « interaction non couverte ») : balayage HORS LIGNE dans le vrai jeu (jeu
public) au début d'un niveau : pour chaque clic candidat (`plafonds.clics`) puis chaque flèche (et SPACE si dispo),
depuis l'état de départ (préfixe rejoué à chaque essai), différence d'image par couleur ; les essais dont l'effet
dépasse celui de la même flèche jouée sans clic sont signalés. Aucune action dans une vraie partie, aucun coût réel.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/balayage_interactions.py <jeu> <niveau> → lignes JSON"""
import json
import os
import sys

import numpy as np

sys.path += [os.path.join(os.path.dirname(__file__), "../T3.0"), os.path.join(os.path.dirname(__file__), "../T3.1")]
os.chdir(os.path.join(os.path.dirname(__file__), "../.."))
import plafonds as pf


def effet(g0, g1):
    """Couleurs dont la position a changé → {couleur: nombre de cases changées}."""
    d = g0 != g1
    out = {}
    for c in set(np.unique(g0[d]).tolist()) | set(np.unique(g1[d]).tolist()):
        out[int(c)] = int(((g0 == c) != (g1 == c)).sum())
    return out


def essai(gid, k, coups):
    env, f = pf.env_au_niveau(gid, k)
    g0 = np.asarray(f.frame[-1])
    for c in coups:
        f = pf.jouer(env, c)
    return effet(g0, np.asarray(f.frame[-1])), f.levels_completed, f.state.name, list(f.available_actions)


def main():
    gid, k = sys.argv[1], int(sys.argv[2])
    env, f = pf.env_au_niveau(gid, k)
    img, dispo = np.asarray(f.frame[-1]), list(f.available_actions)
    fl = [a for a in (1, 2, 3, 4, 5) if a in dispo]
    print(json.dumps({"jeu": gid, "niveau": k, "actions": dispo, "clics": len(pf.clics(img))}), flush=True)
    seul = {a: essai(gid, k, [(a, None, None)])[0] for a in fl}
    for a in fl:
        print(json.dumps({"coup": [a], "effet": seul[a]}), flush=True)
    for c in pf.clics(img):
        e_clic = essai(gid, k, [c])[0]
        for a in fl:
            e, n, etat, _ = essai(gid, k, [c, (a, None, None)])
            neuf = {col: v for col, v in e.items() if col not in seul[a] and col not in e_clic}
            print(json.dumps({"clic": [c[1], c[2]], "puis": a, "effet_clic": e_clic, "effet": e, "neuf": neuf,
                              "niveau": n, "etat": etat}), flush=True)


if __name__ == "__main__":
    main()
