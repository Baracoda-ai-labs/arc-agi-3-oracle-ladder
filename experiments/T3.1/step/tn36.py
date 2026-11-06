"""T3.1 — tn36 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Une action (clic) = une exécution entière animée ; seule l'image finale compte. État privé : compteur de clics (jauge
lente aux niveaux 5-6), sprites remplacés (changement d'échelle = recréation, Scene.retirer plante → on cache).
Constantes (programmes des onglets, positions, rotations, échelles) tirées de la description / des données de niveau."""
import numpy as np

PANNEAU, GRILLE, PIECE, CIBLE, MUR, SAUVE = "plljmx", "grsysj", "bltjrl", "taptxx", "wauzms", "chrccc"
EMETTEUR, FAISCEAU, COLONNE, BIT, PROG, BOUTON, ONGLET, JAUGE = ("laycmuofkkgm", "laycmuommm", "inwola", "Maidxz",
                                                               "takfnb", "sucqgk", "tozzsf", "sthpyh")
CADRE = np.array([[0] * 6, [1, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 1], [1, 0, 1, 1, 0, 1], [1] * 6])
BASE = np.array([[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 0, 0, 1]])
NIVEAUX = {(29, 32): 0, (44, 7): 1, (52, 11): 2, (40, 23): 3, (47, 18): 4, (36, 7): 5, (40, 7): 6}
DONNEES = {  # niveau : (programmes, positions, rotations, échelles) des onglets de démonstration
    1: ([[1, 1, 1, 1], [33, 33, 33, 33]], [[2, 0], [0, 2]], [90, 180], [1, 1]),
    2: ([[3] * 4, [33] * 4, [34] * 4, [2] * 4], [[0, -2], [0, 2], [2, 0], [-2, 0]], [180] * 4, [1] * 4),
    3: ([[34] * 3, [8] * 3, [3] * 3, [9] * 3], [[2, 0], [-3, -3], [0, -2], [-3, -3]], [0] * 4, [1, 1, 1, 4]),
    4: ([[9] * 3, [8] * 3, [3] * 3, [5] * 3, [0, 63, 0]], [[-3, -3], [-3, -3], [0, -2], [0, 0], [-1, -1]], [0] * 5,
        [4, 1, 1, 1, 3]),
    5: ([[3] * 3, [33] * 3, [2] * 3, [1] * 3], [[0, 0]] * 4, [0] * 4, [1] * 4),
    6: ([[3] * 3, [33] * 3, [2] * 3, [1] * 3], [[0, 0]] * 4, [0] * 4, [1] * 4),
}
COUL_DEMO = 4
ST = {}


def _dims(s):
    return s["pixels"].shape[1], s["pixels"].shape[0]


def _dans(s, x, y):
    w, h = _dims(s)
    return s["x"] <= x < s["x"] + w and s["y"] <= y < s["y"] + h


def _vivants(scene, tag):
    return [s for s in scene.par_tag(tag) if id(s) not in ST["morts"]]


def _boites(ax, ay, aw, ah, b):
    bw, bh = _dims(b)
    return not (ax >= b["x"] + bw or ax + aw <= b["x"] or ay >= b["y"] + bh or ay + ah <= b["y"])


def _px(rot, ech, coul):
    p = np.rot90(np.where(BASE > 0, coul, -1), k=(-rot % 360) // 90)
    return np.repeat(np.repeat(p, ech, 0), ech, 1)


def _etat(s):
    p = s["pixels"]
    ech = p.shape[0] // 4
    coul = int(p[p >= 0][0])
    for rot in (0, 90, 180, 270):
        if np.array_equal(_px(rot, ech, coul) >= 0, p >= 0):
            return {"x": s["x"], "y": s["y"], "rot": rot, "ech": ech, "coul": coul}
    raise ValueError("pièce inconnue")


def _cible(scene):
    """(x, y, échelle, rotation, couleur) de la cible au sens du but (cadre décalé de l'échelle)."""
    cs = scene.par_tag(CIBLE)
    if not cs:
        return None
    t = cs[0]
    p = t["pixels"]
    ech = p.shape[0] // 6
    for rot in (0, 90, 180, 270):
        m = np.repeat(np.repeat(np.rot90(CADRE, k=(-rot % 360) // 90), ech, 0), ech, 1)
        if np.array_equal(m > 0, p >= 0):
            return (t["x"] + ech, t["y"] + ech, ech, rot, int(p[p >= 0][0]))
    return None


def _panneau(scene, pan):
    d = {"pan": pan, "dedans": lambda t: [s for s in _vivants(scene, t) if _dans(pan, s["x"], s["y"])]}
    d["piece"] = d["dedans"](PIECE)[0]
    d["murs"] = d["dedans"](MUR)
    d["sauves"] = d["dedans"](SAUVE)
    em = _vivants(scene, EMETTEUR)
    d["lasers"] = []
    for f in d["dedans"](FAISCEAU):
        e = next((e for e in em if e["bloquant"] and f["bloquant"] and _boites(f["x"], f["y"], *_dims(f), e)), None)
        if e is not None:
            d["lasers"].append((f, e))
    d["grille"] = d["dedans"](GRILLE)[0]
    progs = d["dedans"](PROG)
    d["prog"] = progs[0]
    d["lecture"] = "reooao" in d["prog"].get("tags", ())
    bits = sorted([b for b in _vivants(scene, BIT)], key=lambda b: b["y"])
    d["colonnes"] = []
    for c in sorted([c for c in _vivants(scene, COLONNE) if _dans(d["prog"], c["x"], c["y"])], key=lambda c: c["x"]):
        d["colonnes"].append((c, [b for b in bits if _dans(c, b["x"], b["y"])]))
    bt = d["dedans"](BOUTON)
    d["bouton"] = bt[0] if bt else None
    return d


def _init(scene):
    ST["morts"] = set()
    pans = sorted(scene.par_tag(PANNEAU), key=lambda s: s["x"])
    cible = scene.par_tag(CIBLE)
    niv = NIVEAUX.get((cible[0]["x"], cible[0]["y"]), 0) if cible else 0
    g = scene.par_tag(JAUGE)[0]
    d = 1 - g["x"]
    n = ST.get("clics", 0)
    if not (ST.get("niv") == niv and d > 0 and (n // 2 if niv >= 5 else n) == d):
        n = 2 * d if niv >= 5 else d
    ST.update(scene=id(scene), niv=niv, cible=_cible(scene), clics=n, gauche=_panneau(scene, pans[0]), droit=_panneau(scene, pans[1]))


def _couleur(s):
    p = s["pixels"]
    return int(p[p >= 0][0])


def _poser(scene, P, st, vivant):
    """Rend l'état (position, rotation, échelle, couleur, visibilité) sur le sprite de la pièce."""
    s = P["piece"]
    px = _px(st["rot"], st["ech"], st["coul"])
    if px.shape != s["pixels"].shape:
        i = next(k for k, t in enumerate(scene.sprites) if t is s)
        suivants = [t for t in scene.sprites[i + 1:] if t["couche"] == s["couche"] and t["visible"]
                    and id(t) not in ST["morts"]]
        scene.montrer(s, False)
        ST["morts"].add(id(s))
        n = scene.creer(dict(s, pixels=px), st["x"], st["y"])
        P["piece"] = n
        for t in suivants:
            scene.montrer(t, False)
            ST["morts"].add(id(t))
            nt = scene.creer(t, t["x"], t["y"])
            scene.montrer(nt, True)
            for P2 in (ST["gauche"], ST["droit"]):
                for k in ("prog", "grille", "pan"):
                    if P2[k] is t:
                        P2[k] = nt
        s = n
    else:
        for dy in range(px.shape[0]):
            for dx in range(px.shape[1]):
                if s["pixels"][dy, dx] != px[dy, dx]:
                    scene.ecrire(s, dy, dx, int(px[dy, dx]))
    scene.placer(s, st["x"], st["y"])
    scene.montrer(s, vivant)


def _heurte(P, st, s):
    if not s["bloquant"]:
        return False
    w = 4 * st["ech"]
    return _boites(st["x"], st["y"], w, w, s)


def _laser_touche(P, st, f, e, vis):
    return _heurte(P, st, f if vis[id(f)] else e)


def _sauves(P, st, vis_s):
    for c in P["sauves"]:
        vis_s[id(c)] = True
        if _heurte(P, st, c) and _dims(c)[0] // 4 == st["ech"]:
            vis_s[id(c)] = False
            return c
    return None


def _executer(scene, P, codes, depart, reset, but=None):
    vis_l = {id(f): f["visible"] for f, _ in P["lasers"]}
    vis_s = {id(c): c["visible"] for c in P["sauves"]}
    st, vivant = dict(depart), True
    _sauves(P, st, vis_s)

    def tue():
        nonlocal vivant
        vivant = False

    def apres():
        for f, e in P["lasers"]:
            if _laser_touche(P, st, f, e, vis_l):
                tue()
                break
        _sauves(P, st, vis_s)

    def bouge(dx, dy):
        if not vivant:
            return
        st["x"] += dx
        st["y"] += dy
        if any(_heurte(P, st, m) for m in P["murs"]):
            st["x"] -= dx
            st["y"] -= dy
        apres()

    def echelle(dd):
        if not vivant:
            return
        st["ech"] = max(1, st["ech"] + dd)
        if any(_heurte(P, st, m) for m in P["murs"]):
            st["ech"] = max(1, st["ech"] - dd)
        apres()

    def tourne(d):
        st["rot"] = (st["rot"] + d) % 360

    def coul(c):
        st["coul"] = c

    table = {1: lambda: bouge(-4, 0), 2: lambda: bouge(4, 0), 3: lambda: bouge(0, 4), 33: lambda: bouge(0, -4),
             34: lambda: bouge(-4, 0), 10: lambda: bouge(8, 0), 11: lambda: bouge(8, 0), 12: lambda: bouge(-8, 0),
             13: lambda: bouge(-8, 0), 5: lambda: tourne(90), 6: lambda: tourne(-90), 7: lambda: tourne(180),
             16: lambda: tourne(270), 8: lambda: echelle(1), 9: lambda: echelle(-1), 14: lambda: coul(9),
             15: lambda: coul(8), 63: lambda: coul(15)}
    n = len(codes)
    for j, c in enumerate(codes):
        if c in table:
            table[c]()
        if j < n - 1 and j % 3 == 2:
            for f, e in P["lasers"]:
                vis_l[id(f)] = not vis_l[id(f)]
                if vis_l[id(f)] and _heurte(P, st, f):
                    tue()
    if _sauves(P, st, vis_s) is not None:
        depart = dict(st)
    gagne = but is not None and (st["x"], st["y"], st["ech"], st["rot"], st["coul"]) == but
    if not gagne:
        for f, _ in P["lasers"]:
            vis_l[id(f)] = not vis_l[id(f)]
    if reset and not gagne:
        st, vivant = dict(depart), True
        _sauves(P, st, vis_s)
    _poser(scene, P, st, vivant)
    for f, _ in P["lasers"]:
        scene.montrer(f, vis_l[id(f)])
    for c in P["sauves"]:
        scene.montrer(c, vis_s[id(c)])


def _codes(P):
    return [sum(1 << i for i, b in enumerate(bits) if _couleur(b) == 5) for _, bits in P["colonnes"]]


def step(scene, action):
    if ST.get("scene") != id(scene):
        _init(scene)
    kind, r, c = action
    if kind != "CLICK":
        return
    x, y = c, r
    G, D = ST["gauche"], ST["droit"]
    onglets = sorted(_vivants(scene, ONGLET), key=lambda s: s["x"])
    hit = next((k for k, o in enumerate(onglets) if _dans(o, x, y)), None)
    if hit is not None:
        for o in onglets:
            scene.recolorer(o, 9, 2)
        scene.recolorer(onglets[hit], 2, 9)
        progs, poss, rots, echs = DONNEES[ST["niv"]]
        g = G["grille"]
        gw, gh = _dims(g)
        px, py = poss[hit]
        dep = {"x": g["x"] + gw // 4 // 2 * 4 + px * 4, "y": g["y"] + gh // 4 // 2 * 4 + py * 4,
               "rot": rots[hit] % 360, "ech": echs[hit], "coul": COUL_DEMO}
        prog = progs[hit]
        for i, (_, bits) in enumerate(G["colonnes"]):
            if i >= len(prog):
                break
            for k, b in enumerate(bits):
                on = bool(prog[i] & (1 << k))
                cur = _couleur(b)
                new = 5 if on else 1
                if cur != new:
                    scene.recolorer(b, cur, new)
        _executer(scene, G, _codes(G), dep, False)
    elif _dans(D["pan"], x, y):
        if _dans(D["prog"], x, y):
            for col, bits in D["colonnes"]:
                if _dans(col, x, y):
                    for b in bits:
                        if _dans(b, x, y):
                            cur = _couleur(b)
                            scene.recolorer(b, cur, 1 if cur == 5 else 5)
        elif D["bouton"] is not None and _dans(D["bouton"], x, y):
            _executer(scene, D, _codes(D), _etat(D["piece"]), True, ST["cible"])
    ST["clics"] += 1
    if ST["niv"] < 5 or ST["clics"] % 2 == 0:
        g = scene.par_tag(JAUGE)[0]
        scene.deplacer(g, -1, 0)
