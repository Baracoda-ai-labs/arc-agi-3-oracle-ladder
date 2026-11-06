"""T3.1 — ka59 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Une action se résout en plusieurs frames (frappe, glissade, explosion) : on simule toutes les frames et on n'écrit que l'état final.
État privé : rotation des explosifs (invisible quand ils sont tout éteints, table par niveau tirée de ka59.md / source),
directions de poussée mémorisées (glissade sur le fossé en fin d'explosion). Souffles et trait de frappe : temporaires,
retirés avant la fin de l'action, donc jamais créés dans la scène (seul leur masque de collision compte)."""
import numpy as np

PIECE, BLOC, EXPL, CADRE, CIBLE, FOSSE, MUR = ("0022vrxelxosfy", "0001uqqokjrptk", "0003umnkyodpjp", "0010xzmuziohuf",
                                              "0027jbgxilrocf", "0015qniapgwsvb", "0029ifoxxfvvvs")
NIVEAU = {"0028lydaygyjbu": 1, "0030hvaojwefpl": 2, "0031hexyjndrnn": 3, "0032oyluycrfor": 4, "0033lkwljnelik": 5,
          "0034ufzauyukvb": 6, "0035czkjzpboms": 7}
ROTATIONS = {5: [90, 180, 270, 0, 0], 6: [0, 180, 0], 7: [0, 180]}  # par ordre des explosifs dans le niveau
DIR_SOUFFLE = {0: (0, 3), 90: (-3, 0), 180: (0, -3), 270: (3, 0)}
ST = {}


def _masque(s):
    return s["pixels"] != -1


def _touche(a, b, ax=None, ay=None, ma=None):
    """Collision pixel (pixels != -1) de a (éventuellement à une position/masque hypothétique) avec b ; deux tangibles."""
    if a is b or not b.get("bloquant", True) or not b["visible"]:
        return False
    ax = a["x"] if ax is None else ax
    ay = a["y"] if ay is None else ay
    ma = _masque(a) if ma is None else ma
    mb = _masque(b)
    ha, wa = ma.shape
    hb, wb = mb.shape
    x0, x1 = max(ax, b["x"]), min(ax + wa, b["x"] + wb)
    y0, y1 = max(ay, b["y"]), min(ay + ha, b["y"] + hb)
    if x1 <= x0 or y1 <= y0:
        return False
    ra = ma[y0 - ay:y1 - ay, x0 - ax:x1 - ax]
    rb = mb[y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any(ra & rb))


def _objets(scene):
    return [s for s in scene.sprites if s["visible"] and {PIECE, BLOC, EXPL} & set(s.get("tags", ()))]


def _vis(scene, tag):
    return [s for s in scene.par_tag(tag) if s["visible"]]


def _pousser(scene, s, dx, dy):
    """Poussée en chaîne ; seul le mur bloque ; vrai si bloqué (sous-poussées réussies non annulées)."""
    x0, y0 = s["x"], s["y"]
    scene.deplacer(s, dx, dy)
    if any(_touche(s, m) for m in _vis(scene, MUR)):
        scene.placer(s, x0, y0)
        return True
    for o in [o for o in _objets(scene) if _touche(s, o)]:
        if _pousser(scene, o, dx, dy):
            scene.placer(s, x0, y0)
            return True
    return False


def _sur_fosse(scene, s):
    return any(_touche(s, f) for f in _vis(scene, FOSSE))


def _centre(p):
    h, w = p["pixels"].shape
    return (slice(1, 2) if h == 3 else slice(2, 4)), (slice(1, 2) if w == 3 else slice(2, 4))


def _peindre(scene, s, ys, xs, c):
    h, w = s["pixels"].shape
    for y in range(h)[ys]:
        for x in range(w)[xs]:
            scene.ecrire(s, y, x, c)


def _indicateur(scene, sel):
    for p in _vis(scene, PIECE):
        _peindre(scene, p, slice(None), slice(0, 1), 14)
        _peindre(scene, p, slice(None), slice(-1, None), 14)
        _peindre(scene, p, slice(0, 1), slice(None), 14)
        _peindre(scene, p, slice(-1, None), slice(None), 14)
    if sel is None:
        return
    h, w = sel["pixels"].shape
    x, y = sel["x"], sel["y"]
    cotes = [((x, y - 1, np.ones((1, w), bool)), (slice(0, 1), slice(None))),
             ((x, y + h, np.ones((1, w), bool)), (slice(-1, None), slice(None))),
             ((x - 1, y, np.ones((h, 1), bool)), (slice(None), slice(0, 1))),
             ((x + w, y, np.ones((h, 1), bool)), (slice(None), slice(-1, None)))]
    objs = _vis(scene, BLOC) + _vis(scene, EXPL) + _vis(scene, PIECE)
    for (cx, cy, m), (ys, xs) in cotes:
        if any(o is not sel and _touche(sel, o, cx, cy, m) for o in objs):
            _peindre(scene, sel, ys, xs, 0)


def _selection(scene):
    for p in _vis(scene, PIECE):
        ys, xs = _centre(p)
        if np.all(p["pixels"][ys, xs] == 0):
            return p
    return None


def _k(rot):
    return int((-rot % 360) / 90)


def _meche(scene):
    """Chaque explosif allume sa première rangée éteinte (repère non tourné) ; liste de ceux qui viennent d'allumer la dernière."""
    out = []
    for i, e in enumerate(scene.par_tag(EXPL)):
        if not e["visible"]:
            continue
        rot = ST["rot"][i] if i < len(ST["rot"]) else 0
        k = _k(rot)
        P = np.rot90(e["pixels"], -k).copy()
        for r in range(P.shape[0]):
            if P[r, 0] != 12:
                P[r, :] = 12
                if r == P.shape[0] - 1:
                    out.append((i, e, rot))
                break
        R = np.rot90(P, k)
        for y in range(R.shape[0]):
            for x in range(R.shape[1]):
                if e["pixels"][y, x] != R[y, x]:
                    scene.ecrire(e, y, x, int(R[y, x]))
    return out


def _souffle(w, idx, rot):
    n = w + 6 * idx
    m = np.zeros((n, n), bool)
    L = 3 if w == 3 else 3 * idx
    c0 = (n - w) // 2
    m[0:L, c0:c0 + w] = True
    return np.rot90(m, _k((rot + 180) % 360))


def _cle(scene, s):
    for tag in (BLOC, EXPL, PIECE):
        lst = scene.par_tag(tag)
        for i, o in enumerate(lst):
            if o is s:
                return (tag, i)
    return None


def _explosion(scene, expl):
    for idx in (1, 2, 3):
        for i, e, rot in expl:
            w = e["pixels"].shape[1]
            m = _souffle(w, idx, rot)
            bx, by = e["x"] - 3 * idx, e["y"] - 3 * idx
            for o in _vis(scene, BLOC) + _vis(scene, EXPL) + _vis(scene, PIECE):
                if _touche({"x": bx, "y": by}, o, bx, by, m):
                    d = DIR_SOUFFLE[rot]
                    _pousser(scene, o, *d)
                    ST["dirs"][_cle(scene, o)] = d
    for i, e, rot in expl:
        _peindre(scene, e, slice(None), slice(None), 13)
    for _ in range(200):
        bouge = False
        for o in _vis(scene, BLOC) + _vis(scene, EXPL) + _vis(scene, PIECE):
            d = ST["dirs"].get(_cle(scene, o))
            if d is not None and _sur_fosse(scene, o):
                if not _pousser(scene, o, *d):
                    bouge = True
        if not bouge:
            break


def _frappe(scene, tetes, d):
    for o in tetes:
        ST["dirs"][_cle(scene, o)] = d
    for xr in range(500):
        fini = []
        for o in tetes:
            if xr >= 5 and not _sur_fosse(scene, o):
                fini.append(True)
            else:
                fini.append(_pousser(scene, o, *d))
        if all(fini):
            return


def _signature(scene):
    return tuple((s["x"], s["y"]) for s in _objets(scene))


def _init(scene):
    murs = scene.par_tag(MUR)
    niv = NIVEAU.get(murs[0].get("nom") if murs else None, 0)
    sig = _signature(scene)
    if ST.get("niv") != niv or (ST.get("scene") != id(scene) and ST.get("sig0") == sig):
        ST.clear()
        ST.update(niv=niv, rot=ROTATIONS.get(niv, []), dirs={}, sig0=sig)
    ST["scene"] = id(scene)


def step(scene, action):
    _init(scene)
    nom = action[0]
    sel = _selection(scene)
    vec = {"UP": (0, -3), "DOWN": (0, 3), "LEFT": (-3, 0), "RIGHT": (3, 0)}.get(nom)
    if nom == "CLICK":
        h, w = scene.vue
        k = min(int(64 / w), int(64 / h))
        px, py = int((64 - w * k) / 2), int((64 - h * k) / 2)
        r, c = action[1], action[2]
        gx = int((c - px) / k) if c - px >= 0 else -1
        gy = int((r - py) / k) if r - py >= 0 else -1
        if 0 <= gx < w and 0 <= gy < h:
            gx, gy = gx + scene.camera[0], gy + scene.camera[1]
            cible = None
            for s in sorted(scene.sprites, key=lambda s: -s["couche"]):
                if not s.get("bloquant", True) or not s["visible"]:
                    continue
                dx, dy = gx - s["x"], gy - s["y"]
                if 0 <= dy < s["pixels"].shape[0] and 0 <= dx < s["pixels"].shape[1] and s["pixels"][dy, dx] != -1:
                    if PIECE in s.get("tags", ()):
                        cible = s
                        break
            if cible is not None:
                if sel is not None:
                    ys, xs = _centre(sel)
                    _peindre(scene, sel, ys, xs, 4)
                ys, xs = _centre(cible)
                _peindre(scene, cible, ys, xs, 0)
                sel = cible
        _indicateur(scene, sel)
        return
    if vec is None or sel is None:
        return
    x0, y0 = sel["x"], sel["y"]
    scene.deplacer(sel, *vec)
    if any(_touche(sel, m) for m in _vis(scene, FOSSE) + _vis(scene, MUR)):
        scene.placer(sel, x0, y0)
    else:
        tetes = [o for o in _objets(scene) if _touche(sel, o)]
        if tetes:
            scene.placer(sel, x0, y0)
            _frappe(scene, tetes, vec)
    expl = _meche(scene)
    if expl:
        _explosion(scene, expl)
    _indicateur(scene, sel)
