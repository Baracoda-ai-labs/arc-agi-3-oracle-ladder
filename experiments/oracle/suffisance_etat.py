# SPDX-License-Identifier: MIT-0
"""F (CW-445 / CW-451) : TEST DE SUFFISANCE DE L'ÉTAT sur les traces P1 (paquet v2, `experiments/films_p1/combo/fg_g*`,
20 publics, tous niveaux joués). Question : pour une même clé d'état et une même action, voit-on plusieurs successeurs ?
Clé = celle de l'exploration générique de P1 (`generique.Explorateur.cle`) : image sans le bord, ni les cases « compteur »
(petits changements ≤ 4 pixels à 2 cases du bord), apprises ici sur toute la trace du niveau.
Transitions exclues : RESET, et celles qui finissent le niveau ou la vie (état suivant = autre écran).
Cause de chaque désaccord, lue sur la différence entre deux successeurs :
  - « compteur oublié » : ≤ 8 pixels différents, tous à ≤ 4 cases du bord (jauge, horloge non masquées) ;
  - « variable cachée » : différence dans l'aire de jeu (objet ailleurs, autre couleur) : mémoire, horloge interne, élan,
    ou objet apparié autrement → à départager à la main (film, règle).
Usage : uv run python experiments/oracle/suffisance_etat.py → experiments/oracle/suffisance_etat.json"""
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
DOSSIERS = [R / "experiments/films_p1/combo/fg_g0", R / "experiments/films_p1/combo/fg_g1"]


def compteurs(images):
    out = set()
    for a, b in itertools.pairwise(images):
        d = np.argwhere(a != b)
        if 0 < len(d) <= 4:
            for y, x in d:
                if min(x, y, 63 - x, 63 - y) <= 2:
                    out.add((int(x), int(y)))
    return out


def cle(im, cpt):
    m = im.copy()
    m[0, :] = m[-1, :] = 0
    m[:, 0] = m[:, -1] = 0
    for x, y in cpt:
        m[y, x] = 0
    return hashlib.sha1(m.tobytes()).hexdigest()[:16]


def nom_action(a):
    return tuple(a) if isinstance(a, list) else a


def cause(a, b):
    d = np.argwhere(a != b)
    if len(d) <= 8 and all(min(x, y, 63 - x, 63 - y) <= 4 for y, x in d):
        return "compteur oublié"
    return "variable cachée"


def niveau(dossier_niveau):
    z = np.load(dossier_niveau / "partie.npz")
    rows = json.loads((dossier_niveau / "partie.json").read_text())["rows"]
    ims = [np.asarray(x) for x in z["images"]]
    cpt = compteurs(ims)
    succ, vus = {}, {}
    for i, r in enumerate(rows):
        if i + 1 >= len(ims) or r["action"] == 0:
            continue
        fini = "GAME_OVER" in r["state"] or "WIN" in r["state"] or (i > 0 and r["levels_completed"] > rows[i - 1]["levels_completed"])
        if fini:
            continue
        k = (cle(ims[i], cpt), str(nom_action(r["action"])))
        succ.setdefault(k, {}).setdefault(cle(ims[i + 1], cpt), ims[i + 1])
        vus[k] = vus.get(k, 0) + 1
    paires = sum(1 for n in vus.values() if n >= 2)  # puissance du test : seules les paires revues peuvent se contredire
    multiples = {k: v for k, v in succ.items() if len(v) > 1}
    causes = {}
    for v in multiples.values():
        ims_s = list(v.values())
        c = cause(ims_s[0], ims_s[1])
        causes[c] = causes.get(c, 0) + 1
    return paires, len(multiples), causes


def main():
    res = {}
    for d in DOSSIERS:
        for f in sorted(d.glob("*/N*/partie.npz")):
            jeu, niv = f.parent.parent.name, f.parent.name
            p, m, c = niveau(f.parent)
            e = res.setdefault(f"{jeu} {niv}", {"paires": 0, "multiples": 0, "causes": {}})
            e["paires"] += p
            e["multiples"] += m
            for k, v in c.items():
                e["causes"][k] = e["causes"].get(k, 0) + v
    (Path(__file__).parent / "suffisance_etat.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    tp, tm = sum(v["paires"] for v in res.values()), sum(v["multiples"] for v in res.values())
    tc = {}
    for v in res.values():
        for k, n in v["causes"].items():
            tc[k] = tc.get(k, 0) + n
    print(f"niveaux joués : {len(res)} ; paires (clé, action) REVUES au moins 2 fois : {tp} ; à successeurs multiples : {tm} "
          f"({100 * tm / max(1, tp):.1f} %) ; causes : {tc}")
    for k, v in sorted(res.items(), key=lambda kv: -kv[1]["multiples"])[:15]:
        if v["multiples"]:
            print(f"  {k} : {v['multiples']}/{v['paires']} {v['causes']}")


if __name__ == "__main__":
    main()
