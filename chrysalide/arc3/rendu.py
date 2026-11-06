# SPDX-License-Identifier: MIT-0
"""CW-062.2 : « rendu inverse » d'une image ARC-AGI-3 64×64 vers la vraie grille du jeu, sans LLM.
Le moteur arcengine (camera.py) dessine : vue w×h, agrandie par k = min(64 // w, 64 // h) (np.repeat), centrée sur un fond
« letterbox » de couleur unique, puis les interfaces (HUD) par-dessus, à la résolution 64. On inverse exactement cela :
on cherche (k, w, h) tels que l'extérieur soit le letterbox et l'intérieur fait de blocs k×k uniformes, hors cases de HUD.
Sur les 25 jeux publics (niveau 1) : 13 en ×1 (rien à réduire), 9 en ×2 à ×8, 3 en ×1 avec bandes.
Ensuite : sprites = composantes 4-connexes par couleur dans la vraie grille ; `suivre` apparie les sprites d'un coup à
l'autre et regroupe ceux qui bougent ensemble (sprites multi-couleurs, que les composantes seules cassent).
Sortie de `rendu` : {"echelle", "cadre" (y0, x0, h, w en cases 64), "grille" (vraie grille), "fond", "letterbox",
"hud" [(y, x, couleur) en 64], "sprites" [(id, couleur, cases, x, y, couche)]}. Reconstruction exacte : `peindre(r)`."""
from collections import Counter, defaultdict

import numpy as np


def _candidats():
    vus = set()
    for w in range(1, 65):
        for h in range(1, 65):
            k = min(64 // w, 64 // h)
            vus.add((k, w, h))
    # échelle décroissante, puis plus grande vue ; le cadre plein ×1 (toujours cohérent) en tout dernier recours
    return sorted(vus, key=lambda t: (t == (1, 64, 64), -t[0], -t[1] * t[2]))


CANDIDATS = _candidats()


def _ajuste(g, k, w, h, seuil=0.999, seuil_dehors=0.9):
    y0, x0 = (64 - h * k) // 2, (64 - w * k) // 2
    dedans = g[y0:y0 + h * k, x0:x0 + w * k]
    blocs = dedans.reshape(h, k, w, k).transpose(0, 2, 1, 3).reshape(h, w, k * k)
    uniformes = (blocs == blocs[:, :, :1]).all(axis=2)
    if uniformes.mean() < seuil:
        return None
    masque = np.ones(g.shape, dtype=bool)
    masque[y0:y0 + h * k, x0:x0 + w * k] = False
    dehors = g[masque]
    lb = Counter(dehors.tolist()).most_common(1)[0][0] if dehors.size else None
    if dehors.size and (dehors == lb).mean() < seuil_dehors:
        return None
    coul = lb if lb is not None else Counter(np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]]).tolist()).most_common(1)[0][0]
    bords = (dedans[0], dedans[-1], dedans[:, 0], dedans[:, -1])
    if (h * k, w * k) != (64, 64) and any((b == coul).all() for b in bords):
        return None  # la rangée ou colonne extérieure du cadre est entièrement « bande » : elle appartient au letterbox
    return y0, x0, uniformes, lb


def rendu(g64):
    g = np.asarray(g64, dtype=np.int16)
    for k, w, h in CANDIDATS:
        if k == 1 and (w, h) != (64, 64) and (min(64 - w, 64 - h) < 4 and max(64 - w, 64 - h) < 4 or
                                              (w < 64 and 64 - w < 4) or (h < 64 and 64 - h < 4)):
            continue  # ×1 : une bande se reconnaît à au moins 2 cases de chaque côté (vue centrée par le moteur)
        r = _ajuste(g, k, w, h)
        if r is None or (k == 1 and (w, h) != (64, 64) and r[3] is None):
            continue
        y0, x0, _uniformes, lb = r
        dedans = g[y0:y0 + h * k, x0:x0 + w * k]
        blocs = dedans.reshape(h, k, w, k).transpose(0, 2, 1, 3).reshape(h, w, k * k)
        vraie = np.array([[Counter(b.tolist()).most_common(1)[0][0] for b in ligne] for ligne in blocs])
        recon = np.full(g.shape, lb if lb is not None else 0, dtype=np.int16)
        recon[y0:y0 + h * k, x0:x0 + w * k] = np.repeat(np.repeat(vraie, k, 0), k, 1)
        hud = [(int(y), int(x), int(g[y, x])) for y, x in zip(*np.nonzero(recon != g), strict=True)]
        fond = Counter(vraie.ravel().tolist()).most_common(1)[0][0]
        res = {"echelle": k, "cadre": (y0, x0, h * k, w * k), "grille": vraie, "fond": fond, "letterbox": lb, "hud": hud}
        res["sprites"] = sprites(vraie, fond)
        return res
    raise ValueError("aucun rendu cohérent")


def peindre(r):
    """Reconstruit exactement l'image 64×64 : contrôle « sans perte » du rendu inverse."""
    k, (y0, x0, hh, ww) = r["echelle"], r["cadre"]
    out = np.full((64, 64), r["letterbox"] if r["letterbox"] is not None else 0, dtype=np.int16)
    out[y0:y0 + hh, x0:x0 + ww] = np.repeat(np.repeat(r["grille"], k, 0), k, 1)
    for y, x, c in r["hud"]:
        out[y, x] = c
    return out


def sprites(vraie, fond):
    h, w = vraie.shape
    vu = np.zeros((h, w), dtype=bool)
    out = []
    for y in range(h):
        for x in range(w):
            if vu[y, x] or vraie[y, x] == fond:
                continue
            c, pile, cases = vraie[y, x], [(y, x)], []
            vu[y, x] = True
            while pile:
                a, b = pile.pop()
                cases.append((a, b))
                for p, q in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= p < h and 0 <= q < w and not vu[p, q] and vraie[p, q] == c:
                        vu[p, q] = True
                        pile.append((p, q))
            y0, x0 = min(a for a, _ in cases), min(b for _, b in cases)
            out.append((len(out), int(c), sorted((a - y0, b - x0) for a, b in cases), x0, y0, 0))
    return out


def suivre(r0, r1):
    """Apparie les sprites de r0 et r1 (même couleur et même forme ; déplacement minimal), puis regroupe en objets les
    sprites qui ont le MÊME déplacement non nul et se touchent. Rend {"appariement": {id0: (id1, dy, dx)},
    "objets": [[(id1, couleur), …], …] (déplacés ensemble), "nouveaux": [id1], "disparus": [id0]}."""
    libres = defaultdict(list)
    for s in r1["sprites"]:
        libres[(s[1], tuple(s[2]))].append(s)
    app, disparus = {}, []
    for s in sorted(r0["sprites"], key=lambda s: -len(s[2])):
        cand = libres.get((s[1], tuple(s[2])), [])
        if not cand:
            disparus.append(s[0])
            continue
        t = min(cand, key=lambda t: abs(t[3] - s[3]) + abs(t[4] - s[4]))
        cand.remove(t)
        app[s[0]] = (t[0], t[4] - s[4], t[3] - s[3])
    pris = {v[0] for v in app.values()}
    nouveaux = [s[0] for s in r1["sprites"] if s[0] not in pris]
    par_id = {s[0]: s for s in r1["sprites"]}
    bougent = defaultdict(list)
    for i1, dy, dx in app.values():
        if (dy, dx) != (0, 0):
            bougent[(dy, dx)].append(i1)
    objets = []
    for ids in bougent.values():
        cases = {i: {(par_id[i][4] + a, par_id[i][3] + b) for a, b in par_id[i][2]} for i in ids}
        restants = set(ids)
        while restants:
            grp, pile = [], [restants.pop()]
            while pile:
                i = pile.pop()
                grp.append(i)
                for j in list(restants):
                    if any((a + da, b + db) in cases[j] for a, b in cases[i] for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        restants.discard(j)
                        pile.append(j)
            objets.append([(i, par_id[i][1]) for i in sorted(grp)])
    return {"appariement": app, "objets": objets, "nouveaux": nouveaux, "disparus": disparus}


def objets_moteur(env):
    """Perception ORACLE, pour les bancs seulement (jeux publics et synthétiques chargés en local) : sprites lus dans le
    moteur arcengine (nom, position, calque, tags, pixels, collision). Sert à isoler le raisonnement (moteur logique, C)
    de la perception. Jamais disponible sur les jeux cachés : n'entre JAMAIS dans l'agent soumis."""
    jeu = env._game
    cam = jeu.camera
    k, x0, y0 = cam._calculate_scale_and_offset()
    out = []
    for s in jeu.current_level.get_sprites():
        if not s.is_visible:
            continue
        out.append({"id": id(s), "nom": s.name, "x": s.x, "y": s.y, "couche": s.layer, "tags": list(s.tags),
                    "pixels": np.asarray(s.render()).tolist(), "collision": bool(s.is_collidable)})
    return {"echelle": k, "cadre": (y0, x0, cam._height * k, cam._width * k), "vue": (cam._height, cam._width),
            "camera_xy": (getattr(cam, "_x", 0), getattr(cam, "_y", 0)), "sprites": out}
