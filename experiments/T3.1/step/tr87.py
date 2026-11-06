"""T3.1 — dynamique de tr87 exprimée avec les seuls effets de `ontologie_exec.Scene`.
État privé (dans scene._tr87) : listes source/réponse/règles, index du curseur, rotation de chaque glyphe, jauge.
Il est reconstruit depuis la scène quand la scène est neuve (début de niveau ou resynchronisation)."""
import random

import numpy as np

MASQUES = {
    'A1': ['..#..', '..#..', '.###.', '..#..', '#####'],
    'A2': ['....#', '..#.#', '#####', '#.#..', '#....'],
    'A3': ['#####', '#.#..', '#....', '#.#..', '#####'],
    'A4': ['..#..', '#####', '#.#.#', '#.#.#', '..#..'],
    'A5': ['#...#', '#####', '..#..', '#####', '#...#'],
    'A6': ['#####', '..#..', '###..', '#....', '#####'],
    'A7': ['#...#', '#####', '#...#', '#...#', '##.##'],
    'B1': ['#....', '####.', '#..#.', '#..#.', '#####'],
    'B2': ['#####', '#...#', '###.#', '#.#.#', '#####'],
    'B3': ['..###', '..#.#', '#####', '#.#..', '###..'],
    'B4': ['.###.', '.#.#.', '#####', '#...#', '#####'],
    'B5': ['#####', '#...#', '#...#', '#####', '..#..'],
    'B6': ['####.', '#..##', '#...#', '##..#', '.####'],
    'B7': ['..#..', '#####', '#.#.#', '#####', '..#..'],
    'C1': ['#.#.#', '#....', '#.#.#', '#....', '#####'],
    'C2': ['###.#', '#....', '.....', '....#', '#.###'],
    'C3': ['#.###', '..#..', '..#..', '..#..', '###.#'],
    'C4': ['..#..', '#.#.#', '..#..', '#.#.#', '..#..'],
    'C5': ['##.##', '#...#', '#.#.#', '#...#', '##.##'],
    'C6': ['#.###', '#.#.#', '###.#', '.....', '#.#.#'],
    'C7': ['#...#', '.....', '#...#', '##.##', '.#.#.'],
}
TAG = "nxkictbbvzt"
GRAINES_ROT = [4, 2, 1, 2, 12, 20]
PALETTE = [5, 8, 14, 15, 6, 9, 12, 0]


def _px(code, quarts, couleur=5):
    m = np.array([[couleur if c == "#" else -1 for c in r] for r in MASQUES[code]], dtype=np.int16)
    return np.rot90(m, -quarts).copy()


def _code(s):
    return s["nom"][-2:]


def _rots_possibles(s):
    m = s["pixels"] >= 0
    return [q for q in range(4) if np.array_equal(_px(_code(s), q) >= 0, m)]


def _curseur_px(n, bas):
    w = 7 * n - 2
    plein, bords = [0] * w, [0] + [-1] * (w - 2) + [0]
    return np.array([bords, plein] if bas else [plein, bords], dtype=np.int16)


def _glyphe_sous(glyphes, x, y):
    for g in glyphes:  # boîte englobante, comme get_sprite_at en mode BOUNDING_BOX
        if g["x"] <= x < g["x"] + 5 and g["y"] <= y < g["y"] + 5:
            return g
    return None


def _init(scene):
    glyphes = sorted(scene.par_tag(TAG), key=lambda s: (s["y"], s["x"]))
    fond_y = next(s for s in scene.sprites if s.get("nom") == "background")["y"]
    bas = [g for g in glyphes if g["y"] > fond_y]
    y0 = min(g["y"] for g in bas)
    source = [g for g in bas if g["y"] == y0]
    reponse = [g for g in bas if g["y"] != y0]
    regles = []
    for f in sorted((s for s in scene.sprites if s.get("nom") == "iqrduxrukrk"), key=lambda s: (s["y"], s["x"])):
        L = [_glyphe_sous(glyphes, f["x"], f["y"])]
        while (v := next((g for g in glyphes if g["x"] == L[0]["x"] - 7 and g["y"] == L[0]["y"]), None)):
            L.insert(0, v)
        R = [_glyphe_sous(glyphes, f["x"] + f["pixels"].shape[1], f["y"])]
        while (v := next((g for g in glyphes if g["x"] == R[-1]["x"] + 7 and g["y"] == R[-1]["y"]), None)):
            R.append(v)
        regles.append((L, R))
    # rotation cachée : graine du niveau, contrôlée par les pixels (les glyphes symétriques à 180° sont ambigus)
    poss = [_rots_possibles(g) for g in glyphes]
    rot = None
    for gr in GRAINES_ROT:
        rng = random.Random(gr)
        cand = [[0, 90, 180, 270].index(rng.choice([0, 90, 180, 270])) for _ in glyphes]
        if all(c in p for c, p in zip(cand, poss)):
            rot = cand
            break
    if rot is None:
        rot = [p[0] if p else 0 for p in poss]
    rots = {id(g): q for g, q in zip(glyphes, rot)}
    alter = fond_y in (38, 41)
    curs = sorted((s for s in scene.sprites if s.get("nom", "").startswith("qvtymdcqear")), key=lambda s: s["y"])
    edit = [e for r in regles for e in r] if alter else [[g] for g in reponse]
    idx = next((i for i, e in enumerate(edit) if curs and e[0]["x"] == curs[0]["x"] and e[0]["y"] == curs[0]["y"] + 4), 0)
    return {"source": source, "reponse": reponse, "regles": regles, "rots": rots, "alter": alter,
            "double": fond_y in (37, 41), "arbre": fond_y == 41, "dernier": fond_y == 41,
            "curseur": curs, "idx": idx, "jauge": 256 if fond_y == 41 else 128}


def _editables(E):
    return [e for r in E["regles"] for e in r] if E["alter"] else [[g] for g in E["reponse"]]


def _poser_curseur(scene, E):
    e = _editables(E)[E["idx"]]
    g = e[0]
    haut, bas = E["curseur"]
    if E["alter"] and haut["pixels"].shape[1] != 7 * len(e) - 2:  # largeur du curseur = longueur de la suite
        nh = scene.creer(dict(haut, visible=True, pixels=_curseur_px(len(e), False)), haut["x"], haut["y"])
        nb = scene.creer(dict(bas, visible=True, pixels=_curseur_px(len(e), True)), bas["x"], bas["y"])
        scene.montrer(haut, False)  # Scene.retirer plante (list.remove compare des tableaux) : on cache
        scene.montrer(bas, False)
        haut, bas = nh, nb
        E["curseur"] = [haut, bas]
    scene.placer(haut, g["x"], g["y"] - 4)
    scene.placer(bas, g["x"], g["y"] + 5 - 2 + 4)


def _changer(scene, E, g, d):
    c = _code(g)
    nc = c[0] + str((int(c[1]) + d - 1) % 7 + 1)
    q = E["rots"].pop(id(g))
    scene.montrer(g, False)  # au lieu de retirer (voir plus haut)
    n = scene.creer(dict(g, visible=True, nom=g["nom"][:-2] + nc, pixels=_px(nc, q)), g["x"], g["y"])
    E["rots"][id(n)] = q
    return n


def _noms_egaux(lst, i, motif):
    return i + len(motif) <= len(lst) and all(_code(lst[i + k]) == _code(motif[k]) for k in range(len(motif)))


def _test(E):
    src, rep, regles = E["source"], E["reponse"], E["regles"]
    i = j = 0
    segs, halos = [], []
    while i < len(src):
        for L, R in regles:
            if not _noms_egaux(src, i, L):
                continue
            inter = []
            if E["arbre"]:
                nouv, saute = [], False
                for g in R:
                    for L2, R2 in regles:
                        if _code(L2[0]) == _code(g):
                            nouv += R2
                            inter += [g] + L2
                            break
                    else:
                        saute = True
                        break
                if saute:
                    continue
                R = nouv
            elif E["double"]:
                for L2, R2 in regles:
                    if all(_code(a) == _code(b) for a, b in zip(R, L2)):
                        inter = R + L2
                        R = R2
                        break
                else:
                    continue
            if not _noms_egaux(rep, j, R):
                return None
            segs.append(src[i:i + len(L)] + rep[j:j + len(R)])
            halos.append(L + R + inter)
            i += len(L)
            j += len(R)
            break
        else:
            return None
    return segs, halos


def step(scene, action):
    E = getattr(scene, "_tr87", None)
    if E is None:
        E = scene._tr87 = _init(scene)
    a = action[0]
    if a in ("LEFT", "RIGHT"):
        n = len(_editables(E))
        E["idx"] = (E["idx"] + (-1 if a == "LEFT" else 1)) % n
        E["jauge"] -= 1
        _poser_curseur(scene, E)
    elif a in ("UP", "DOWN"):
        d = -1 if a == "UP" else 1
        if E["alter"]:
            suite = _editables(E)[E["idx"]]
            for k in range(len(suite)):
                suite[k] = _changer(scene, E, suite[k], d)
        else:
            E["reponse"][E["idx"]] = _changer(scene, E, E["reponse"][E["idx"]], d)
        E["jauge"] -= 1
        res = _test(E)
        if res is not None:
            for c in E["curseur"]:
                scene.montrer(c, False)
            segs, halos = res
            poses = []
            modele_halo = {"nom": "nxkictbbvztedxeenecwqa", "tags": [], "pixels": np.zeros((9, 9), np.int16),
                           "couche": -2, "visible": True}
            for s, (seg, hs) in enumerate(zip(segs, halos)):
                for f in range(1, len(PALETTE)):
                    for g in seg:
                        scene.recolorer(g, PALETTE[f - 1], PALETTE[f])
                    if f == 1:
                        for h in poses:
                            scene.montrer(h, False)
                        poses = [scene.creer(modele_halo, g["x"] - 2, g["y"] - 2) for g in hs]
            scene.gagner() if E["dernier"] else scene.niveau_suivant()
            return
    else:
        return
    if E["jauge"] <= 0:
        scene.perdre()
