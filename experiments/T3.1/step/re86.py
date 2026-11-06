"""T3.1 — re86 : dynamique reproduite avec les seuls effets de ontologie_exec.Scene (lecture de pixels = requête)."""
import numpy as np

PIECE, CREUX, XPLEIN, MUR, POT, CIBLE = "0031cppcuvqlbi", "0036ilsgwuvbxv", "0049ppblgltcfi", "0003dlchiwseii", "0007dtbisvazhv", "0054xnsuqceejm"
PAS = 3


def _dim(s):
    return s["pixels"].shape  # (h, w)


def _couleur(s):
    p = s["pixels"]
    return int(p[(p != 0) & (p != -1)][0])


def _centre_sel(s):
    h, w = _dim(s)
    return s["pixels"][h // 2, w // 2] == 0


def _touche(a, b):
    ah, aw = _dim(a)
    bh, bw = _dim(b)
    x0, x1 = max(a["x"], b["x"]), min(a["x"] + aw, b["x"] + bw)
    y0, y1 = max(a["y"], b["y"]), min(a["y"] + ah, b["y"] + bh)
    if x1 <= x0 or y1 <= y0:
        return False
    ra = a["pixels"][y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]]
    rb = b["pixels"][y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra != -1) & (rb != -1)))


def _barres(s):
    p = s["pixels"]
    h, w = p.shape
    col = next((c for c in range(w) if np.all(p[:, c] != -1)), w - 1)
    lig = next((r for r in range(h) if np.all(p[r, :] != -1)), h - 1)
    return col, lig


def _centre_naturel(scene, s):
    h, w = _dim(s)
    if CREUX in s.get("tags", ()):
        scene.ecrire(s, h // 2, w // 2, -1)
        return
    c = _couleur(s)
    if XPLEIN in s.get("tags", ()):
        scene.ecrire(s, h // 2, w // 2, c)
        return
    col, lig = _barres(s)
    scene.ecrire(s, h // 2, w // 2, c if (h // 2 == lig or w // 2 == col) else -1)


def _remodeler(scene, s, pixels):
    """Changement de forme : pas d'effet natif → retirer puis recréer s et les sprites qui le suivent (ordre conservé)."""
    i = scene.sprites.index(s)
    suite = scene.sprites[i:]
    for t in suite:
        scene.retirer(t)
    nouveau = None
    for t in suite:
        if t is s:
            nouveau = scene.creer(dict(t, pixels=pixels), t["x"], t["y"])
        else:
            scene.creer(t, t["x"], t["y"])
    return nouveau


def _deformer(scene, s, dh, dw):
    h, w = _dim(s)
    scene.ecrire(s, h // 2, w // 2, -1)
    c = _couleur(s)
    px = np.full((h + dh, w + dw), -1, dtype=np.int16)
    px[:, 0] = px[:, -1] = px[0, :] = px[-1, :] = c
    px[px.shape[0] // 2, px.shape[1] // 2] = 0
    return _remodeler(scene, s, px)


def _mur_creux(scene, s, m, dx, dy):
    h, w = _dim(s)
    if dx != 0:
        if w > 6:
            s = _deformer(scene, s, 3, -3)
            scene.deplacer(s, 0, h // 2 - (h + 3) // 2)
            scene.deplacer(s, 0, round(s["y"] / 3) * 3 - s["y"])
            if dx < 0:
                scene.deplacer(s, -dx, -dy)
        else:
            scene.deplacer(s, -dx, -dy)
    elif dy != 0:
        if h > 6:
            s = _deformer(scene, s, -3, 3)
            scene.deplacer(s, w // 2 - (w + 3) // 2, 0)
            scene.deplacer(s, round(s["x"] / 3) * 3 - s["x"], 0)
            if dy < 0:
                scene.deplacer(s, -dx, -dy)
        else:
            scene.deplacer(s, -dx, -dy)


def _mur_croix(scene, s, m, dx, dy):
    c = _couleur(s)
    col, lig = _barres(s)
    h, w = _dim(s)
    mh, mw = _dim(m)
    V = m["x"] <= s["x"] + col < m["x"] + mw
    H = m["y"] <= s["y"] + lig < m["y"] + mh
    ch, cw = h // 2, w // 2

    def glisse_col(dc):
        scene.ecrire(s, slice(None), col, -1)
        scene.ecrire(s, slice(None), col + dc, c)
        scene.ecrire(s, lig, col, c)
        scene.ecrire(s, ch, cw, 0)

    def glisse_lig(dl):
        scene.ecrire(s, lig, slice(None), -1)
        scene.ecrire(s, lig + dl, slice(None), c)
        scene.ecrire(s, lig, col, c)
        scene.ecrire(s, ch, cw, 0)

    if dx != 0:
        a, b = (-3, 3) if dx > 0 else (3, -3)
        n1 = col > 0 if dx > 0 else col < w - 2
        n2 = col < w - 2 if dx > 0 else col > 0
        if V and H:
            scene.deplacer(s, -dx, -dy)
        elif V:
            if n1:
                glisse_col(a)
            else:
                scene.deplacer(s, -dx, -dy)
        elif H:
            scene.deplacer(s, -dx, -dy)
            if n2:
                glisse_col(b)
    elif dy != 0:
        a, b = (-3, 3) if dy > 0 else (3, -3)
        n1 = lig > 0 if dy > 0 else lig < h - 2
        n2 = lig < h - 2 if dy > 0 else lig > 0
        if H and V:
            scene.deplacer(s, -dx, -dy)
        elif H:
            if n1:
                glisse_lig(a)
            else:
                scene.deplacer(s, -dx, -dy)
        elif V:
            scene.deplacer(s, -dx, -dy)
            if n2:
                glisse_lig(b)


def _peindre(scene, s, pot):
    c = int(pot["pixels"][1, 1])
    h, w = _dim(s)
    ph, pw = _dim(pot)
    for i in range(h):
        for j in range(w):
            if pot["x"] <= s["x"] + j < pot["x"] + pw and pot["y"] <= s["y"] + i < pot["y"] + ph and s["pixels"][i, j] != -1:
                scene.ecrire(s, i, j, c)
    for _ in range(500):  # frames d'animation de la même action
        p = s["pixels"]
        if not np.any(p[p != -1] != c):
            break
        for i, j in np.argwhere(p == c).tolist():
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    a, b = i + di, j + dj
                    if 0 <= a < h and 0 <= b < w and s["pixels"][a, b] != -1:
                        scene.ecrire(s, a, b, c)
    scene.ecrire(s, h // 2, w // 2, 0)


def _deplacer(scene, s, dx, dy):
    vh, vw = scene.vue
    scene.deplacer(s, dx, dy)
    h, w = _dim(s)
    cx, cy = s["x"] + w // 2, s["y"] + h // 2
    if not (0 <= cx < vw and 0 <= cy < vh):
        scene.deplacer(s, -dx, -dy)
        return
    for m in scene.par_tag(MUR):
        if _touche(s, m):
            if CREUX in s.get("tags", ()):
                _mur_creux(scene, s, m, dx, dy)
                return
            _mur_croix(scene, s, m, dx, dy)
    _centre_naturel(scene, s)
    for pot in scene.par_tag(POT):
        if _touche(s, pot) and _couleur(s) != int(pot["pixels"][1, 1]):
            _peindre(scene, s, pot)
            return
    h, w = _dim(s)
    scene.ecrire(s, h // 2, w // 2, 0)


def _motif(scene):
    toile = np.full((64, 64), -1, dtype=np.int16)
    for s in scene.par_tag(PIECE):
        p = s["pixels"]
        h, w = p.shape
        y0, y1, x0, x1 = max(0, s["y"]), min(64, s["y"] + h), max(0, s["x"]), min(64, s["x"] + w)
        if y1 > y0 and x1 > x0:
            r = p[y0 - s["y"]:y1 - s["y"], x0 - s["x"]:x1 - s["x"]]
            m = r != -1
            toile[y0:y1, x0:x1][m] = r[m]
    for c in scene.par_tag(CIBLE):
        p = c["pixels"]
        if np.any((p != -1) & (p != 4) & (p != toile[:p.shape[0], :p.shape[1]])):
            return False
    return True


def step(scene, action):
    nom = action[0]
    pieces = scene.par_tag(PIECE)
    sel = [s for s in pieces if _centre_sel(s)]
    d = {"UP": (0, -PAS), "DOWN": (0, PAS), "LEFT": (-PAS, 0), "RIGHT": (PAS, 0)}
    if nom in d:
        if sel:
            _deplacer(scene, sel[0], *d[nom])
    elif nom == "SPACE":
        if not sel:
            return
        i = pieces.index(sel[0])
        suiv = pieces[(i + 1) % len(pieces)]
        for s in pieces:
            _centre_naturel(scene, s)
        h, w = _dim(suiv)
        scene.ecrire(suiv, h // 2, w // 2, 0)
    else:
        return
    if _motif(scene):
        scene.niveau_suivant()
