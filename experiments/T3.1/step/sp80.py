"""T3.1 — sp80 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Phase réglage seulement visible coup par coup : un versement (SPACE) joue tout l'écoulement en une transition ; s'il
réussit, le niveau change (non mesuré) ; s'il rate, tout est remis (gouttes créées effacées, couleurs restaurées, pièces
gardées) et la sélection revient à la pièce la plus proche de l'origine. La jauge (HUD) n'est pas dans l'image.
Rotation 180 (niv. 2, 3, 5) : flèches inversées, clic (63-x, 63-y)."""
import numpy as np

BARRE, DEVIATEUR, COUPE = "plzwjbfyfli", "tuvkdkhdokr", "repwkzbkhxl"
VEC = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
INVERSE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}


def _vis(scene, tag):
    return [s for s in scene.par_tag(tag) if s["visible"]]


def _pieces(scene):
    return _vis(scene, BARRE) + _vis(scene, DEVIATEUR)


def _tourne(scene):
    """Niveaux 2, 3 (16×16, 3 coupes) et 5 (20×20, un seul déviateur) sont affichés tournés de 180°."""
    if scene.vue[0] == 16:
        return len(_vis(scene, COUPE)) >= 3
    return len(_vis(scene, DEVIATEUR)) == 1


def _selection(scene):
    for s in _pieces(scene):
        if np.any(s["pixels"] == 9):
            return s
    return None


def _relacher(scene, s):
    c = 15 if DEVIATEUR in s.get("tags", ()) else 8
    scene.recolorer(s, 9, c)
    scene.calque(s, 0)


def _choisir(scene, s):
    ancienne = _selection(scene)
    if ancienne is not None:
        _relacher(scene, ancienne)
    p = s["pixels"]
    for dy in range(p.shape[0]):
        for dx in range(p.shape[1]):
            if p[dy, dx] >= 0 and p[dy, dx] != 4:
                scene.ecrire(s, dy, dx, 9)
    scene.calque(s, 1)


def _chevauche_pixel(a, b, ax, ay):
    ha, wa = a["pixels"].shape
    hb, wb = b["pixels"].shape
    x0, x1 = max(ax, b["x"]), min(ax + wa, b["x"] + wb)
    y0, y1 = max(ay, b["y"]), min(ay + ha, b["y"] + hb)
    if x1 <= x0 or y1 <= y0:
        return False
    ra = a["pixels"][y0 - ay:y1 - ay, x0 - ax:x1 - ax]
    rb = b["pixels"][y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra >= 0) & (rb >= 0)))


def _permis(scene, s, x, y):
    """Zone interdite : y < 3, ou boîte entrant dans la boîte d'une coupe élargie de 1 px."""
    if y < 3:
        return False
    h, w = s["pixels"].shape
    for c in _vis(scene, COUPE):
        ch, cw = c["pixels"].shape
        if x < c["x"] + cw + 1 and x + w > c["x"] - 1 and y < c["y"] + ch + 1 and y + h > c["y"] - 1:
            return False
    return True


def _deplacer(scene, s, dx, dy):
    x, y = s["x"] + dx, s["y"] + dy
    if not _permis(scene, s, x, y):
        return
    for o in scene.sprites:
        if o is s or not o["visible"] or not o.get("bloquant", True):
            continue
        if _chevauche_pixel(s, o, x, y):
            t = o.get("tags", ())
            if BARRE not in t and DEVIATEUR not in t:
                return  # bloqué par cadre, mur, goutte, coupe ou source
    scene.deplacer(s, dx, dy)


def step(scene, action):
    nom = action[0]
    tourne = _tourne(scene)
    if nom in VEC:
        s = _selection(scene)
        if s is not None:
            _deplacer(scene, s, *VEC[INVERSE[nom] if tourne else nom])
    elif nom == "CLICK":
        r, c = action[1], action[2]
        if tourne:
            r, c = 63 - r, 63 - c
        h, w = scene.vue
        k = min(64 // w, 64 // h)
        px, py = (64 - w * k) // 2, (64 - h * k) // 2
        if c - px < 0 or r - py < 0:
            return
        gx, gy = (c - px) // k, (r - py) // k
        if gx >= w or gy >= h:
            return
        for s in _pieces(scene):
            ph, pw = s["pixels"].shape
            if s["x"] <= gx < s["x"] + pw and s["y"] <= gy < s["y"] + ph:
                _choisir(scene, s)
                return
    elif nom == "SPACE":
        # Écoulement raté (le réussi change de niveau) : remise, puis sélection par défaut (min x²+y², ordre barres puis déviateurs).
        ps = _pieces(scene)
        if ps:
            _choisir(scene, min(ps, key=lambda s: s["x"] ** 2 + s["y"] ** 2))
