"""T3.1 — sk48 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Bras télescopiques (tête + segments), blocs portés/poussés, guides de translation, pastilles, UNDO par instantanés."""
import numpy as np

PAS = 6
TETE, SEG, BLOC, GUIDE, MUR, ZONE = "epdquznwmq", "qtjqovumxf", "elmjchdqcn", "irkeobngyh", "mkgqjopcjn", "jtteddgeyl"
DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
MOTIF_SEG = np.array([[-2] * 6, [-2] * 6, [3, 2, 2, 3, 2, 2], [2, 2, 3, 2, 2, 3], [-2] * 6, [-2] * 6])


# ------------------------------------------------------------------ requêtes
def _dir_tete(t):
    p = t["pixels"]
    if p[2, 5] == -1:
        return (1, 0)
    if p[5, 2] == -1 or p[5, 3] == -1:
        return (0, 1)
    if p[2, 0] == -1:
        return (-1, 0)
    return (0, -1)


def _horiz(s):
    return bool((s["pixels"][2, :] >= 0).all())


def _segs(scene):
    return [s for s in scene.sprites if s.get("nom") == SEG and s["visible"]]


def _seg_at(scene, x, y, horiz, sauf=None):
    for s in _segs(scene):
        if s is not sauf and s["x"] == x and s["y"] == y and _horiz(s) == horiz:
            return s
    return None


def _bloc_at(st, x, y):
    for b in st["blocs"]:
        if b["x"] == x and b["y"] == y:
            return b
    return None


def _sprite_at(scene, x, y, tag):
    """get_sprite_at du moteur : calque décroissant, boîte, pixel != -1, tag."""
    for s in sorted(scene.sprites, key=lambda s: -s["couche"]):
        p = s["pixels"]
        if s.get("bloquant", True) and s["x"] <= x < s["x"] + p.shape[1] and s["y"] <= y < s["y"] + p.shape[0]:
            if p[y - s["y"], x - s["x"]] == -1:
                continue
            if tag in s.get("tags", ()):
                return s
    return None


def _bloque(scene, st, s, mx, my):
    z = st["zone"]
    x, y = s["x"] + mx * PAS, s["y"] + my * PAS
    h, w = s["pixels"].shape
    zh, zw = z["pixels"].shape
    if x < z["x"] or x + w > z["x"] + zw or y < z["y"] or y + h > z["y"] + zh:
        return True
    return _sprite_at(scene, x, y, MUR) is not None


# ------------------------------------------------------------------ état privé
def _init(scene):
    st = {"tetes": scene.par_tag(TETE), "blocs": scene.par_tag(BLOC), "zone": scene.par_tag(ZONE)[0],
          "pending": False, "had": None}
    st["bras"] = {}
    for t in st["tetes"]:
        mx, my = _dir_tete(t)
        h = mx != 0
        chaine, s = [], _seg_at(scene, t["x"], t["y"], h)
        while s is not None and all(s is not c for c in chaine):
            chaine.append(s)
            s = _seg_at(scene, s["x"] + mx * PAS, s["y"] + my * PAS, h)
        st["bras"][id(t)] = chaine
    st["paire"] = {}
    for t in st["tetes"]:
        if t["y"] < 53:
            p = next((b for b in st["tetes"] if b is not t and b["pixels"][2, 2] == t["pixels"][2, 2]), None)
            if p is not None:
                st["paire"][id(t)] = p
    # actif : tête dont l'anneau est 0, sinon bras dont un segment porte la couleur 1, sinon la première
    actif = next((t for t in st["tetes"] if t["y"] < 53 and (t["pixels"] == 0).any()), None)
    if actif is None:
        actif = next((t for t in st["tetes"] if t["y"] < 53 and any((s["pixels"] == 1).any() for s in st["bras"][id(t)])),
                     st["tetes"][0])
    st["actif"] = actif
    pastilles = [s for s in scene.sprites if s.get("nom") == "kevthtkmzm"]
    st["past"] = {}
    for p in st["paire"].values():
        st["past"][id(p)] = [next((q for q in pastilles if q["x"] == s["x"] + 1 and q["y"] == s["y"] + 1), None)
                             for s in st["bras"][id(p)][1:]]
    st["hist"] = [_instantane(st)]
    scene._sk = st
    return st


def _instantane(st):
    return ([(t, t["x"], t["y"], len(st["bras"][id(t)])) for t in st["tetes"]] +
            [(b, b["x"], b["y"], 0) for b in st["blocs"]])


def _teinter(scene, st, actif, on):
    for t in (actif, st["paire"].get(id(actif))):
        if t is None:
            continue
        if on:
            scene.recolorer(t, 4, 0)
            for s in st["bras"][id(t)]:
                scene.recolorer(s, 2, 1)
                scene.recolorer(s, 3, 2)
        else:
            scene.recolorer(t, 0, 4)
            for s in st["bras"][id(t)]:
                scene.recolorer(s, 1, 2)
                scene.recolorer(s, 2, 3)


def _sur_bras(st, t):
    return [b for s in st["bras"][id(t)] if (b := _bloc_at(st, s["x"], s["y"])) is not None]


def _pastilles(scene, st):
    ok = True
    for h, m in st["paire"].items():
        th = next(t for t in st["tetes"] if id(t) == h)
        bh, bm = _sur_bras(st, th), _sur_bras(st, m)
        for i, q in enumerate(st["past"][id(m)]):
            vis = i < len(bh) and bh[i]["pixels"][1, 1] == bm[i]["pixels"][1, 1]
            ok = ok and vis
            if q is not None:
                scene.montrer(q, vis)
    return ok


def _nouveau_seg(scene, x, y, horiz, couche):
    s = scene.creer({"nom": SEG, "tags": [SEG], "pixels": MOTIF_SEG, "couche": couche, "visible": True,
                     "bloquant": True}, x, y)
    if not horiz:
        scene.tourner(s, 1)
    return s


def _oter(scene, s):
    """retirer() compare des dicts contenant des tableaux numpy (list.remove -> ==) et lève ValueError : on cache."""
    scene.montrer(s, False)


# ------------------------------------------------------------------ poussée (bnrdrdiakd)
def _pousser(scene, st, s, mx, my, faits, porteur=None):
    if id(s) in faits:
        return True
    est_seg = s.get("nom") == SEG
    if _bloque(scene, st, s, mx, my):
        if not (est_seg and ((_dir_seg(s) == (-mx, -my)) or _bloque(scene, st, s, 0, 0))):
            return False
    dx, dy = mx * PAS, my * PAS
    if est_seg:
        for ox, oy in ((0, 0), (dx, dy)):
            b = _bloc_at(st, s["x"] + ox, s["y"] + oy)
            if b is not None:
                if _pousser(scene, st, b, mx, my, faits, porteur=s):
                    faits[id(b)] = b
                elif _horiz(s) != (mx != 0):  # bloc bloqué en travers du rail : le segment est bloqué
                    return False
                elif _seg_at(scene, b["x"], b["y"], mx != 0) is None:  # bloc bloqué hors rail : cadre
                    st["cadres"] = True
    else:
        hz = mx != 0
        for ox, oy in ((0, 0), (dx, dy)):
            k = _seg_at(scene, s["x"] + ox, s["y"] + oy, not hz, sauf=porteur)
            if k is not None and _horiz(k) != hz:
                return False
        w = _bloc_at(st, s["x"] + dx, s["y"] + dy)
        if w is not None and not _pousser(scene, st, w, mx, my, faits):
            return False
        if _seg_at(scene, s["x"], s["y"], hz) is None and _seg_at(scene, s["x"] + dx, s["y"] + dy, hz) is not None:
            st["cadres"] = True
    faits[id(s)] = s
    return True


def _dir_seg(s):
    return (1, 0) if _horiz(s) else (0, 1)


def _fin_coup(scene, st):
    """Fin d'animation : test du but ; sinon instantané."""
    if _pastilles(scene, st):
        return  # clignotement puis niveau suivant (transition non mesurée)
    st["hist"].append(_instantane(st))


def _fleche(scene, st, mx, my):
    t = st["actif"]
    bras = st["bras"][id(t)]
    bx, by = _dir_tete(t)
    faits = {}
    st["cadres"] = False
    if (mx, my) == (bx, by):
        if _bloque(scene, st, bras[-1], mx, my):
            return
        for s in list(bras):
            _pousser(scene, st, s, mx, my, faits)
        n = _nouveau_seg(scene, t["x"], t["y"], mx != 0, 1 if mx != 0 else 0)
        scene.recolorer(n, 2, 1)
        scene.recolorer(n, 3, 2)
        bras.insert(0, n)
    elif (mx, my) == (-bx, -by):
        if len(bras) == 1:
            return
        st["had"] = bras.pop(0)
        for s in list(bras):
            _pousser(scene, st, s, mx, my, faits)
    elif _sprite_at(scene, t["x"] + 2 + mx * 3, t["y"] + 2 + my * 3, GUIDE) is not None:
        for s in list(bras):
            if not _pousser(scene, st, s, mx, my, faits):
                if st["cadres"]:
                    st["pending"] = True
                return
        faits[id(t)] = t
    else:
        return
    if faits:
        for s in faits.values():
            scene.deplacer(s, mx * PAS, my * PAS)
        if st["had"] is not None:
            _oter(scene, st["had"])
            st["had"] = None
        _fin_coup(scene, st)
    elif st["cadres"]:
        st["pending"] = True


def _undo(scene, st):
    if len(st["hist"]) < 2:
        return
    st["hist"].pop()
    prec = st["hist"][-1]
    for t in st["tetes"]:
        for s in st["bras"][id(t)]:
            _oter(scene, s)
        st["bras"][id(t)] = []
    for spr, x, y, n in prec:
        scene.placer(spr, x, y)
        if TETE in spr.get("tags", ()):
            mx, my = _dir_tete(spr)
            for i in range(n):
                st["bras"][id(spr)].append(_nouveau_seg(scene, x + i * mx * PAS, y + i * my * PAS, mx != 0,
                                                        1 if mx != 0 else 0))
    _teinter(scene, st, st["actif"], True)
    _pastilles(scene, st)


def step(scene, action):
    st = getattr(scene, "_sk", None) or _init(scene)
    kind = action[0]
    if kind in ("SPACE", "RESET"):
        return
    if st["pending"]:  # coup consommé par la fin d'une animation restée en suspens
        st["pending"] = False
        _fin_coup(scene, st)
        return
    if kind == "CLICK":
        c = _sprite_at(scene, action[2], action[1], "sys_click")
        if c is not None:
            for h, m in st["paire"].items():
                th = next(t for t in st["tetes"] if id(t) == h)
                if (c is th or c is m) and th is not st["actif"]:
                    _teinter(scene, st, st["actif"], False)
                    st["actif"] = th
                    _teinter(scene, st, th, True)
                    break
    elif kind == "UNDO":
        _undo(scene, st)
    elif kind in DIRS:
        _fleche(scene, st, *DIRS[kind])
