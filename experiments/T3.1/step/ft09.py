"""T3.1 — ft09 : step(scene, action) avec les seuls effets fermés de Scene (recolorer). Pas d'import du jeu."""

# palette par niveau (description ft09.md) ; le niveau est reconnu par (nb de cibles, présence de tuiles à motif)
PALETTES = {(1, False): [9, 8], (2, False): [9, 12], (4, False): [8, 12], (3, False): [9, 8, 12],
            (8, True): [14, 15], (4, True): [11, 14]}
VOIS = [[(-1, -1), (0, -1), (1, -1)], [(-1, 0), (0, 0), (1, 0)], [(-1, 1), (0, 1), (1, 1)]]


def _tuile(scene, x, y, tag):
    """Premier sprite bloquant portant `tag` dont la boîte contient (x, y), calque le plus haut d'abord."""
    for s in sorted(scene.sprites, key=lambda s: -s["couche"]):
        h, w = s["pixels"].shape
        if s.get("bloquant", True) and s["x"] <= x < s["x"] + w and s["y"] <= y < s["y"] + h:
            if s["pixels"][y - s["y"], x - s["x"]] < 0:
                continue
            if tag in s.get("tags", ()):
                return s
    return None


def step(scene, action):
    if action[0] != "CLICK":
        return
    h, w = scene.vue
    k = min(64 // w, 64 // h)
    px, py = (64 - w * k) // 2, (64 - h * k) // 2
    gx = (action[2] - px) // k if action[2] - px >= 0 else -1
    gy = (action[1] - py) // k if action[1] - py >= 0 else -1
    if not (0 <= gx < w and 0 <= gy < h):
        return
    gx, gy = gx + scene.camera[0], gy + scene.camera[1]
    t = _tuile(scene, gx, gy, "Hkx")
    motif = False
    if t is None:
        t = _tuile(scene, gx, gy, "NTi")
        motif = t is not None
    if t is None:
        return  # clic vide : le clignotement du cadre (niveau 1) finit sur sa couleur d'origine
    pal = PALETTES[(len(scene.par_tag("bsT")), bool(scene.par_tag("NTi")))]
    masque = [[1 if t["pixels"][j][i] == 6 else 0 for i in range(3)] for j in range(3)] if motif else \
        [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
    if motif:
        masque[1][1] = 1
    x0, y0 = t["x"], t["y"]
    for i in range(3):
        for j in range(3):
            if masque[j][i]:
                dx, dy = VOIS[j][i]
                v = _tuile(scene, x0 + 4 * dx, y0 + 4 * dy, "Hkx") or _tuile(scene, x0 + 4 * dx, y0 + 4 * dy, "NTi")
                if v is not None:
                    c = int(v["pixels"][1][1])
                    scene.recolorer(v, c, pal[(pal.index(c) + 1) % len(pal)])
