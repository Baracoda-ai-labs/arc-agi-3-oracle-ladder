"""T3.1 — su15 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Un clic = toute l'animation interne (4 frames + prolongations de recul) simulée ici ; seule l'image finale compte.
État privé : pile d'annulation (instantanés fruits/ennemis), pixels d'origine des icônes et cibles, ordre des listes.
Constantes reprises de su15.md (tailles/couleurs des fruits, masques des ennemis, somme 2^k requise par niveau)."""
import numpy as np

FRUIT, CIBLE, ICONE, MAIN = "zmlxwcvwb", "xkstxyqbs", "rgjznrcin", "ooutlqdaq"
T_ENN = {"ybnveypak": 1, "ybnveypak2": 2, "ybnveypak3": 3}
TAG_ENN = {v: k for k, v in T_ENN.items()}
TAILLES = [1, 2, 3, 4, 5, 7, 8, 9, 10]
COULEURS = [10, 6, 15, 11, 12, 8, 9, 7, 14]
CALQUES = {0: 10, 1: 9, 8: 2}
_E = -2
MASQUES = {1: [[_E, _E, 7, _E, _E], [_E, 7, _E, 7, _E], [7, _E, _E, _E, 7], [_E, 7, 7, 7, _E]],
           2: [[-1, -1, 14, -1, -1], [-1, 14, -1, 14, -1], [14, -1, 14, -1, 14], [-1, 14, -1, 14, -1]],
           3: [[13, _E, 13, _E, 13], [_E, 13, _E, 13, _E], [13, 13, 13, 13, 13], [_E, 13, 13, 13, _E]]}
# somme 2^k requise (buts « fruit » seulement), indexée par les positions des cibles
REQUIS = {((44, 11),): 4, ((29, 23),): 8, ((5, 46), (19, 46)): 12, ((1, 53),): 8, ((28, 11),): 8,
          ((2, 12), (52, 53)): 8, ((19, 13), (40, 18)): 16, ((3, 15), (3, 51), (52, 15), (52, 51)): 32,
          ((7, 37), (7, 51), (49, 51)): 20}
RAYON, PAS, NFR, Y0, Y1 = 8, 4, 4, 10, 63
ST = {}


def _wh(s):
    return s["pixels"].shape[1], s["pixels"].shape[0]


def _centre(s):
    w, h = _wh(s)
    return s["x"] + w // 2, s["y"] + h // 2


def _recouvre(a, b):
    wa, ha = _wh(a)
    wb, hb = _wh(b)
    return not (a["x"] + wa <= b["x"] or b["x"] + wb <= a["x"] or a["y"] + ha <= b["y"] or b["y"] + hb <= a["y"])


def _proche(px, py, s):
    w, h = _wh(s)
    cx = min(max(px, s["x"]), s["x"] + w - 1)
    cy = min(max(py, s["y"]), s["y"] + h - 1)
    return (px - cx) ** 2 + (py - cy) ** 2 <= RAYON * RAYON


def _borne(scene, s, x, y):
    w, h = _wh(s)
    H, W = scene.vue
    x = min(max(x, 0), W - w)
    y = max(y, Y0)
    y = min(y, Y1, H - h)
    return x, y


def _niv(s):
    return TAILLES.index(s["pixels"].shape[0])


def _typ(s):
    return next(T_ENN[t] for t in s.get("tags", ()) if t in T_ENN)


def _vis(scene, tag):
    return [s for s in scene.par_tag(tag) if s["visible"]]


def _enn(scene):
    return [s for s in scene.sprites if s["visible"] and any(t in T_ENN for t in s.get("tags", ()))]


def _creer_fruit(scene, k, x, y, couche=None):
    px = np.full((TAILLES[k], TAILLES[k]), COULEURS[k], dtype=np.int16)
    m = {"nom": str(k), "tags": [str(k), FRUIT], "pixels": px, "couche": CALQUES.get(k, 0) if couche is None else couche,
         "visible": True, "bloquant": True}
    return scene.creer(m, x, y)


def _creer_enn(scene, t, x, y):
    m = {"nom": TAG_ENN[t], "tags": [TAG_ENN[t]], "pixels": np.array(MASQUES[t], dtype=np.int16), "couche": -1,
         "visible": True, "bloquant": True}
    return scene.creer(m, x, y)


def _instantane(F, E):
    return [("f", _niv(s), s["x"], s["y"]) for s in F] + [("e", _typ(s), s["x"], s["y"]) for s in E]


def _rouge(scene):
    return any(np.any(c["pixels"] == 2) for c in _vis(scene, CIBLE))


def _somme(F):
    return sum(1 << _niv(s) for s in F)


def _sync(scene):
    cibles = tuple(sorted((c["x"], c["y"]) for c in scene.par_tag(CIBLE)))
    if ST.get("sid") == id(scene):
        return
    F, E = _vis(scene, FRUIT), _enn(scene)
    snap = _instantane(F, E)
    if ST.get("sig") != cibles:
        ST.clear()
        ST.update(sig=cibles, requis=REQUIS.get(cibles, 0), init=snap, pile=[snap], orig={})
        if not _rouge(scene):
            ST["orig"] = {(s["nom"], s["x"], s["y"]): s["pixels"].copy() for s in scene.par_tag(ICONE) + scene.par_tag(CIBLE)}
    elif snap == ST["init"]:
        ST["pile"] = [snap]
    ST.update(sid=id(scene), F=F, E=E)


def _recolorer_tout(scene, couleur):
    for s in scene.par_tag(ICONE) + scene.par_tag(CIBLE):
        for c in np.unique(s["pixels"]):
            if c >= 0 and c != couleur:
                scene.recolorer(s, int(c), couleur)


def _restaurer_hud(scene):
    for s in scene.par_tag(ICONE) + scene.par_tag(CIBLE):
        o = ST["orig"].get((s["nom"], s["x"], s["y"]))
        if o is None or o.shape != s["pixels"].shape:
            continue
        for dy, dx in zip(*np.nonzero(o != s["pixels"])):
            scene.ecrire(s, int(dy), int(dx), int(o[dy, dx]))


def _annuler(scene):
    if not ST["pile"]:
        return
    snap = ST["pile"].pop()
    for s in _vis(scene, FRUIT) + _enn(scene):
        scene.montrer(s, False)
    F, E = [], []
    for kind, v, x, y in snap:
        if kind == "f":
            F.append(_creer_fruit(scene, v, x, y))
        else:
            E.append(_creer_enn(scene, v, x, y))
    ST["F"], ST["E"] = F, E
    if _rouge(scene) and _somme(F) >= ST["requis"]:
        _restaurer_hud(scene)


class Erreur(Exception):
    pass


def _clic(scene, gx, gy):
    F, E = list(ST["F"]), list(ST["E"])
    selF = [f for f in F if _proche(gx, gy, f)]
    selE = [e for e in E if _proche(gx, gy, e)]
    u1, p1 = {}, {}
    for e in selE:
        if _typ(e) == 1:
            cx, cy = _centre(e)
            dx, dy = float(gx) - cx, float(gy) - cy
            d = (dx * dx + dy * dy) ** 0.5
            u1[id(e)] = (dx / d, dy / d) if d > 0 else (0.0, 0.0)
            p1[id(e)] = (float(e["x"]), float(e["y"]))
    hits = {}  # id(fruit) -> état du recul
    imm = {}  # id(ennemi) -> frames d'immunité
    st = {"xw": 0}

    def ids(lst):
        return {id(s) for s in lst}

    def glisse():
        return any(not h["kill"] and 4 <= h["t"] < 8 for h in hits.values())

    def retirer_fruit(f):
        scene.montrer(f, False)
        for lst in (F, selF):
            if any(x is f for x in lst):
                lst[:] = [x for x in lst if x is not f]
        hits.pop(id(f), None)

    def retirer_enn(e):
        scene.montrer(e, False)
        for lst in (E, selE):
            lst[:] = [x for x in lst if x is not e]
        imm.pop(id(e), None)
        u1.pop(id(e), None)
        p1.pop(id(e), None)

    def remplacer_fruit(f, k):
        n = _creer_fruit(scene, k, f["x"], f["y"], couche=f["couche"])
        scene.montrer(f, False)
        for lst in (F, selF):
            for i, x in enumerate(lst):
                if x is f:
                    lst[i] = n
        hits[id(n)] = hits.pop(id(f))
        hits[id(n)]["s"] = n
        return n

    def fusion_ennemis():
        n = len(E)
        if n < 2:
            return
        par = list(range(n))

        def r(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(n):
            for j in range(i + 1, n):
                if not _recouvre(E[i], E[j]):
                    continue
                if _typ(E[i]) != _typ(E[j]):
                    raise Erreur
                a, b = r(i), r(j)
                if a != b:
                    par[b] = a
        grp = {}
        for i in range(n):
            grp.setdefault(r(i), []).append(E[i])
        for g in grp.values():
            if len(g) < 2:
                continue
            t = _typ(g[0])
            if t < 3:
                cx = sum(_centre(e)[0] for e in g) // len(g)
                cy = sum(_centre(e)[1] for e in g) // len(g)
                ne = _creer_enn(scene, t + 1, 0, 0)
                w, h = _wh(ne)
                scene.placer(ne, *_borne(scene, ne, cx - w // 2, cy - h // 2))
                E.append(ne)
                imm[id(ne)] = NFR
            for e in g:
                retirer_enn(e)

    def fusion_fruits():
        fusion_ennemis()
        n = len(selF)
        if n < 2:
            return
        par = list(range(n))

        def r(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(n):
            for j in range(i + 1, n):
                if not _recouvre(selF[i], selF[j]):
                    continue
                if _niv(selF[i]) != _niv(selF[j]):
                    raise Erreur
                a, b = r(i), r(j)
                if a != b:
                    par[b] = a
        grp = {}
        for i in range(n):
            grp.setdefault(r(i), []).append(selF[i])
        for g in grp.values():
            if len(g) < 2:
                continue
            k = _niv(g[0])
            if k < 8:
                cx = sum(_centre(f)[0] for f in g) // len(g)
                cy = sum(_centre(f)[1] for f in g) // len(g)
                s = TAILLES[k + 1]
                nf = _creer_fruit(scene, k + 1, 0, 0)
                scene.placer(nf, *_borne(scene, nf, cx - s // 2, cy - s // 2))
                F.append(nf)
            for f in g:
                retirer_fruit(f)

    def frapper(e, f):
        k = _niv(f)
        fx, fy = _centre(f)
        ex, ey = _centre(e)
        vx, vy = float(fx - ex), float(fy - ey)
        d = vx * vx + vy * vy
        if d > 0:
            d = d ** 0.5
            vx, vy = vx / d, vy / d
        else:
            vx, vy = 0.0, -1.0
        hits[id(f)] = {"s": f, "t": 0, "b": (float(f["x"]), float(f["y"])), "v": (vx, vy),
                       "p": (float(f["x"]), float(f["y"])), "kill": k <= 0, "nk": k - 1 if k > 0 else None}
        imm[id(e)] = 9

    def recul():
        fini = []
        for h in list(hits.values()):
            f, t = h["s"], h["t"]
            dfy = 4 if h["kill"] else 8
            bx, by = h["b"]
            px, py = h["p"]
            if t < 4:
                px, py = bx, by + {1: -1.0, 3: 1.0}.get(t % 4, 0.0)
            else:
                if h["nk"] is not None:
                    f = remplacer_fruit(f, h["nk"])
                    h["nk"] = None
                px += h["v"][0] * 2.5
                py += h["v"][1] * 2.5
                h["p"] = (px, py)
            scene.placer(f, *_borne(scene, f, int(round(px)), int(round(py))))
            h["t"] = t + 1
            if h["t"] >= dfy:
                fini.append(h)
        for h in fini:
            if h["kill"]:
                retirer_fruit(h["s"])
            else:
                hits.pop(id(h["s"]), None)

    def frame():
        g = glisse()
        for s in list(selF) + list(selE):
            if id(s) in hits:
                continue
            est_enn = any(x is s for x in E)
            if est_enn and g:
                continue
            if id(s) in u1:
                ux, uy = u1[id(s)]
                fx, fy = p1[id(s)]
                fx += ux * (PAS * 0.85)
                fy += uy * (PAS * 0.85)
                nx, ny = _borne(scene, s, int(round(fx)), int(round(fy)))
                p1[id(s)] = (float(nx), float(ny))
            else:
                cx, cy = _centre(s)
                dx, dy = gx - cx, gy - cy
                nx = s["x"] + (min(PAS, dx) if dx > 0 else max(-PAS, dx) if dx < 0 else 0)
                ny = s["y"] + (min(PAS, dy) if dy > 0 else max(-PAS, dy) if dy < 0 else 0)
                nx, ny = _borne(scene, s, nx, ny)
            scene.placer(s, nx, ny)
        # sgmsqapcxe
        g = glisse()
        if hits:
            recul()
        for k in list(imm):
            if imm[k] > 0:
                imm[k] -= 1
            if imm[k] <= 0:
                del imm[k]
        if st["xw"] < NFR and E and F and not g:
            sel = ids(selE)
            immun = set(imm)
            for e in E:
                if id(e) in sel or id(e) in immun:
                    continue
                libres = [f for f in F if id(f) not in hits]
                if not libres:
                    break
                ex, ey = _centre(e)
                best, bd = None, None
                for f in libres:
                    fx, fy = _centre(f)
                    d = (fx - ex) ** 2 + (fy - ey) ** 2
                    if bd is None or d < bd:
                        best, bd = f, d
                tx, ty = _centre(best)
                sp = 2 if _typ(e) == 3 else 1
                dx = sp if tx > ex else -sp if tx < ex else 0
                dy = sp if ty > ey else -sp if ty < ey else 0
                scene.placer(e, *_borne(scene, e, e["x"] + dx, e["y"] + dy))
            if F:
                for e in list(E):
                    if id(e) in immun or id(e) in sel:
                        continue
                    for f in list(F):
                        if id(f) in hits:
                            continue
                        if _recouvre(e, f):
                            frapper(e, f)
                fusion_ennemis()
        st["xw"] += 1
        if st["xw"] < NFR:
            return True
        return bool(hits)

    fusionne = False
    while True:
        cont = frame()
        if not fusionne and st["xw"] >= NFR:
            fusionne = True
            fusion_fruits()
        if not cont:
            break
    ST["F"], ST["E"] = F, E


def step(scene, action):
    _sync(scene)
    kind, row, col = action
    if kind == "UNDO":
        _annuler(scene)
        return
    if kind != "CLICK":
        return
    gx, gy = col, row
    ST["pile"].append(_instantane(ST["F"], ST["E"]))
    mains = [m for m in scene.par_tag(MAIN) if m["visible"]]
    for m in mains:
        w, h = _wh(m)
        if m["x"] <= gx < m["x"] + w and m["y"] <= gy < m["y"] + h:
            scene.placer(m, 500, m["y"])
            break
    if gy <= Y0 - 1 or gy >= Y1:
        return
    try:
        _clic(scene, gx, gy)
    except Erreur:
        _annuler(scene)
        return
    F = ST["F"]
    if _somme(F) < ST["requis"]:
        _recolorer_tout(scene, 2)
    if mains and F and (F[0]["x"], F[0]["y"]) != (3, 58):
        scene.placer(mains[0], 500, mains[0]["y"])
