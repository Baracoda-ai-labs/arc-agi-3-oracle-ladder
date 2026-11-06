"""[G] CCM-282-C / CCM-032-H : VÉRITÉ MESURÉE « quel objet, cliqué, change la sélection » au début d'un niveau public,
dans le VRAI jeu, hors partie (préfixe `plafonds.env_au_niveau`, rejoué à chaque essai). Objets = scène perçue de C
(`Trajectoire([image]).etats[0]` → `moteur._sprite`), format de `experiments/T3.0/cas_exploration.py`.
Pilote = objet perçu dont des cases changent sous une flèche depuis le départ. Pour chaque autre objet (hors fonds > ¼) :
clic sur sa case visible la plus centrale (en pixels : x·s + ox), puis chaque flèche ; il est SÉLECTIONNABLE si, pour une
flèche, les cases changées par la flèche après le clic diffèrent de celles changées par la flèche seule ET touchent l'objet.
Témoin (`temoin_ressemblance.classer`) noté à côté, pour choisir les cas par catégorie AVANT toute réponse de Qwen.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/verite_selection.py <jeu> <niveau>… → lignes JSON"""
import json
import os
import sys

import numpy as np

sys.path += [os.path.join(os.path.dirname(__file__), "../T3.0"), os.path.join(os.path.dirname(__file__), "../T3.1")]
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.join(os.path.dirname(__file__), "../.."))
import plafonds as pf
from temoin_ressemblance import classer

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.moteur import _sprite

FL = (1, 2, 3, 4)


def image_apres(gid, k, coups):
    env, f = pf.env_au_niveau(gid, k)
    for c in coups:
        f = pf.jouer(env, c)
    return np.asarray(f.frame[-1])


def cases_pixels(o, tr):
    px = np.asarray(o["pixels"])
    ys, xs = np.nonzero(px >= 0)
    return {(int((o["x"] + x) * tr.s + tr.ox), int((o["y"] + y) * tr.s + tr.oy)) for y, x in zip(ys, xs)}, (ys, xs)


def mesurer(gid, k):
    g0 = image_apres(gid, k, [])
    tr = Trajectoire([g0.tolist()], [])
    sp = [_sprite(o) for o in tr.etats[0]]
    aire = g0.shape[0] * g0.shape[1] / 4
    chg = {}
    for a in FL:
        d = image_apres(gid, k, [(a, None, None)]) != g0
        chg[a] = {(int(x), int(y)) for y, x in zip(*np.nonzero(d))}
    pil = [i for i, o in enumerate(sp) if any(cases_pixels(o, tr)[0] & chg[a] for a in FL)]
    pilote = max(pil, key=lambda i: sum(len(cases_pixels(sp[i], tr)[0] & chg[a]) for a in FL)) if pil else None
    selection = []
    for i, o in enumerate(sp):
        cs, (ys, xs) = cases_pixels(o, tr)
        if i == pilote or not len(xs) or len(cs) > aire:
            continue
        j = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
        cx, cy = int((o["x"] + xs[j]) * tr.s + tr.ox), int((o["y"] + ys[j]) * tr.s + tr.oy)
        clic = (6, cy, cx)
        gc = image_apres(gid, k, [clic])
        for a in FL:
            d = image_apres(gid, k, [clic, (a, None, None)]) != gc
            ch = {(int(x), int(y)) for y, x in zip(*np.nonzero(d))}
            if ch != chg[a] and ch & cs:
                selection.append(i)
                break
    rang = None
    if pilote is not None:
        ordre = [next(i for i, x in enumerate(sp) if x is o) for _s, o in classer(sp, pilote, (g0.shape[1], g0.shape[0]))]
        rang = {i: ordre.index(i) + 1 for i in selection if i in ordre}
        top = ordre[:3]
    else:
        top = []
    return {"jeu": gid, "niveau": k, "objets": len(sp), "pilote": pilote, "selectionnables": selection,
            "rang_temoin": rang, "temoin_top3": top}, {"jeu": gid, "niveau": k, "sprites_depart": sp,
                                                       "taille": tr.taille, "fond": tr.fond, "pilote": pilote}


def main():
    args = sys.argv[1:]
    for gid, k in zip(args[::2], args[1::2]):
        try:
            ligne, _ = mesurer(gid, int(k))
        except Exception as e:  # noqa: BLE001
            ligne = {"jeu": gid, "niveau": int(k), "erreur": f"{type(e).__name__}: {e}"[:200]}
        print(json.dumps(ligne, default=str), flush=True)


if __name__ == "__main__":
    main()
