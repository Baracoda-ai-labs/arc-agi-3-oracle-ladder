"""T3.1 — dynamique d'ar25 avec les seuls effets de `ontologie_exec.Scene`.
État privé (module) : sélection, pile d'annulation, rotations dormantes ; remis à zéro quand une scène neuve apparaît
au départ d'un niveau (cibles différentes ou positions initiales retrouvées)."""
from collections import deque

PIECE, MIROIR, FIXE, CIBLE, REFLET = "0006lxjtqggkmi", "0003uqrdzdofso", "0056icpryeujyf", "0001sruqbuvukh", "0000gezzfvumef"
VERT, HORIZ = "0054kgxrvfihgm", "0002nuguepuujf"
SEUL_V, SEUL_H = "0038pnuzypawco", "reflect_horizontal_only"
ROT_V, ROT_H = "0040bwgtiqvhtu", "0044qlxgcpzowy"
COUL_REFLET = 4
DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}

_E = {}  # état privé


def _tags(s):
    return s.get("tags", ())


def _pieces(scene):
    return scene.par_tag(PIECE)


def _miroirs(scene):
    return scene.par_tag(MIROIR)


def _signature(scene):
    return tuple(sorted((s["x"], s["y"]) for s in scene.par_tag(CIBLE)))


def _positions(scene):
    return [(s["x"], s["y"]) for s in _pieces(scene) + _miroirs(scene)]


def _distance(s, m):
    if VERT in _tags(m):
        return abs(s["x"] + s["pixels"].shape[1] // 2 - m["x"])
    return abs(s["y"] + s["pixels"].shape[0] // 2 - m["y"])


def _miroir(scene, tag):
    return next((m for m in _miroirs(scene) if tag in _tags(m)), None)


def _init(scene):
    sig = _signature(scene)
    idx = lambda lst: [scene.sprites.index(s) for s in lst]  # noqa: E731
    if _E.get("sig") == sig and _E.get("pos0") != _positions(scene):
        _E["ids"] = (idx(_pieces(scene)), idx(_miroirs(scene)))  # resynchronisation : on garde l'état
        scene._ar25 = True
        return
    mob_m = [m for m in _miroirs(scene) if FIXE not in _tags(m)]
    mob_p = [p for p in _pieces(scene) if FIXE not in _tags(p)]
    sel = mob_m[0] if mob_m else mob_p[0] if mob_p else None
    cycle = mob_m + mob_p
    rot = {}
    for i, p in enumerate(_pieces(scene)):
        m = _miroir(scene, VERT) if ROT_V in _tags(p) else _miroir(scene, HORIZ) if ROT_H in _tags(p) else None
        if (ROT_V in _tags(p) or ROT_H in _tags(p)) and m is not None:
            rot[i] = _distance(p, m)
    _E.clear()
    _E.update(sig=sig, pos0=_positions(scene), sel=None if sel is None else scene.sprites.index(sel),
              cycle=[scene.sprites.index(s) for s in cycle], pile=[], rot=rot)
    scene._ar25 = True


def _orbite(scene, groupe, h, w):
    """Grille h×w : reflets (couleur 4, BFS ≤ 12 sur les miroirs) puis pixels réels, comme le moteur."""
    g = [[-1] * w for _ in range(h)]
    miroirs = _miroirs(scene)
    for s in reversed(groupe):
        vus, file = set(), deque()
        px = s["pixels"]
        for dy in range(px.shape[0]):
            for dx in range(px.shape[1]):
                if px[dy, dx] != -1:
                    c = (s["x"] + dx, s["y"] + dy)
                    if 0 <= c[0] < w and 0 <= c[1] < h and c not in vus:
                        vus.add(c)
                        file.append((c, 0))
        while file:
            (x, y), d = file.popleft()
            if d > 12:
                continue
            for m in miroirs:
                if VERT in _tags(m):
                    n, k = (2 * m["x"] - x, y), VERT
                elif HORIZ in _tags(m):
                    n, k = (x, 2 * m["y"] - y), HORIZ
                else:
                    continue
                if (SEUL_H in _tags(s) and k != HORIZ) or (SEUL_V in _tags(s) and k != VERT):
                    continue
                if n in vus:
                    continue
                vus.add(n)
                file.append((n, d + 1))
                if 0 <= n[0] < w and 0 <= n[1] < h and g[n[1]][n[0]] == -1:
                    g[n[1]][n[0]] = COUL_REFLET
    for s in groupe:
        px = s["pixels"]
        for dy in range(px.shape[0]):
            for dx in range(px.shape[1]):
                if px[dy, dx] != -1:
                    x, y = s["x"] + dx, s["y"] + dy
                    if 0 <= x < w and 0 <= y < h:
                        g[y][x] = int(px[dy, dx])
    return g


def _reflets(scene):
    h, w = scene.vue
    ps = _pieces(scene)
    groupes = {0: [p for p in ps if SEUL_V not in _tags(p) and SEUL_H not in _tags(p)],
               -1: [p for p in ps if SEUL_V in _tags(p)], -2: [p for p in ps if SEUL_H in _tags(p)]}
    cibles = {r["couche"]: r for r in scene.par_tag(REFLET)}
    grilles = {}
    for couche, groupe in groupes.items():
        g = _orbite(scene, groupe, h, w)
        grilles[couche] = g
        r = cibles.get(couche)
        if r is None:
            continue
        px = r["pixels"]
        for y in range(min(h, px.shape[0])):
            for x in range(min(w, px.shape[1])):
                if px[y, x] != g[y][x]:
                    scene.ecrire(r, y, x, g[y][x])
    return grilles


def _gagne(scene, grilles):
    for c in scene.par_tag(CIBLE):
        if all(grilles[k][c["y"]][c["x"]] < 0 for k in grilles):
            return False
    return True


def _tourner_centre(scene, s):
    hh, ww = s["pixels"].shape
    cx, cy = s["x"] + ww // 2, s["y"] + hh // 2
    scene.tourner(s, -1)  # np.rot90 du moteur = sens antihoraire
    nh, nw = s["pixels"].shape
    scene.placer(s, cx - nw // 2, cy - nh // 2)


def step(scene, action):
    if not getattr(scene, "_ar25", False):
        _init(scene)
    nom, r, c = action
    sp = scene.sprites
    sel = None if _E["sel"] is None else sp[_E["sel"]]
    h, w = scene.vue
    if nom == "UNDO":
        if _E["pile"]:
            etat = _E["pile"].pop()
            for p, (x, y) in zip(_pieces(scene), etat["p"]):
                scene.placer(p, x, y)
            for k, x, y in etat["m"]:
                if k:
                    m = _miroir(scene, k)
                    if m is not None:
                        scene.placer(m, x, y)
            _reflets(scene)
        return
    if nom in DIRS and sel is not None:
        if FIXE in _tags(sel):
            return
        dx, dy = DIRS[nom]
        t = _tags(sel)
        if MIROIR in t and VERT in t:
            dy = 0
        if MIROIR in t and HORIZ in t:
            dx = 0
        nx, ny = sel["x"] + dx, sel["y"] + dy
        hh, ww = sel["pixels"].shape
        if (nx < 0 or nx + ww > w) and not (MIROIR in t and HORIZ in t):
            return
        if (ny < 0 or ny + hh > h) and not (MIROIR in t and VERT in t):
            return
        bouge = dx != 0 or dy != 0
        if bouge:
            _E["pile"].append({"p": [(p["x"], p["y"]) for p in _pieces(scene)],
                               "m": [(VERT if VERT in _tags(m) else HORIZ if HORIZ in _tags(m) else "", m["x"], m["y"])
                                     for m in _miroirs(scene)]})
        scene.deplacer(sel, dx, dy)
        if bouge:
            ps = _pieces(scene)
            for i, d0 in list(_E["rot"].items()):
                p = ps[i]
                m = _miroir(scene, VERT) if ROT_V in _tags(p) else _miroir(scene, HORIZ)
                if m is not None and _distance(p, m) != d0:
                    _tourner_centre(scene, p)
                    _E["rot"][i] = _distance(p, m)
        if _gagne(scene, _reflets(scene)):
            scene.niveau_suivant()
        return
    if nom == "SPACE":
        cyc = _E["cycle"]
        if cyc:
            i = cyc.index(_E["sel"]) if _E["sel"] in cyc else -1
            _E["sel"] = cyc[(i + 1) % len(cyc)]
        return
    if nom == "CLICK":
        gx, gy = c // 3, r // 3  # caméra échelle 3, sans bande (63 px)
        if 0 <= gx < w and 0 <= gy < h and c < 3 * w and r < 3 * h:
            sous = sorted(scene.a(gx, gy), key=sp.index)
            ps = [s for s in sous if PIECE in _tags(s) and FIXE not in _tags(s)]
            choix = None
            if ps:
                ps.sort(key=lambda s: 1 if SEUL_H in _tags(s) else 2 if SEUL_V in _tags(s) else 3, reverse=True)
                choix = ps[0]
            else:
                ms = [s for s in sous if MIROIR in _tags(s) and FIXE not in _tags(s)]
                if len(ms) == 1:
                    choix = ms[0]
                elif ms:
                    v = next((s for s in ms if VERT in _tags(s)), None)
                    o = next((s for s in ms if HORIZ in _tags(s)), None)
                    if sel is None or sel not in ms:
                        choix = v or o
                    elif sel is v:
                        choix = o
                    elif sel is o:
                        choix = v
                    else:
                        choix = v or o
            if choix is not None:
                _E["sel"] = sp.index(choix)
        if _E["sel"] is None:
            mob = [m for m in _miroirs(scene) if FIXE not in _tags(m)] + [p for p in _pieces(scene) if FIXE not in _tags(p)]
            _E["sel"] = sp.index(mob[0]) if mob else None
        return
