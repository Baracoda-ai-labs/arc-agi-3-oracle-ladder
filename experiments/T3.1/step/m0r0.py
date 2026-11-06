"""T3.1 — m0r0 : dynamique du jeu exprimée avec les seuls effets fermés de `ontologie_exec.Scene`.
État privé : attribut `scene._m0r0` (mode, bloc sélectionné, fusionnés) ; positions de départ du niveau gardées dans un
cache de module indexé par la signature du niveau (mur + vue), pour survivre aux resynchronisations du banc."""
import numpy as np

JUMEAUX = ["pikgci-toljda-leklkn", "pikgci-toljda-rivmdg", "pikgci-boweok-leklkn", "pikgci-boweok-rivmdg"]
MIROIR = {"pikgci-toljda-leklkn": (1, 1), "pikgci-toljda-rivmdg": (-1, 1),
          "pikgci-boweok-leklkn": (1, -1), "pikgci-boweok-rivmdg": (-1, -1)}
COULEURS = ["grwjuk", "orfrpe", "puvdux"]
VECT = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0), "SPACE": (0, 0)}
_DEPARTS = {}  # signature du niveau -> {index sprite: (x, y)}


def _nom(s):
    return s.get("nom", "")


def _couleur(s):
    v = s["pixels"][s["pixels"] >= 0]
    return int(v[0]) if v.size else None


def _repeindre(scene, s, c):  # color_remap(None, c) d'un sprite : chaque couleur présente -> c
    for old in set(int(v) for v in np.unique(s["pixels"]) if v >= 0 and v != c):
        scene.recolorer(s, old, c)


_INTANG = set()  # id() des jumeaux fusionnés (INTANGIBLE : visibles, non collidables) — état privé, sans effet visuel


def _collidable(s):
    return s["visible"] and s.get("bloquant", True) and id(s) not in _INTANG


def _chevauche(a, b):
    pa, pb = a["pixels"], b["pixels"]
    x0, y0 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x1 = min(a["x"] + pa.shape[1], b["x"] + pb.shape[1])
    y1 = min(a["y"] + pa.shape[0], b["y"] + pb.shape[0])
    if x1 <= x0 or y1 <= y0:
        return False
    ra = pa[y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]] >= 0
    rb = pb[y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]] >= 0
    return bool((ra & rb).any())


def _collision(s, o):
    return s is not o and _collidable(s) and _collidable(o) and _chevauche(s, o)


def _sprite_a(scene, x, y, tag):  # get_sprite_at(x, y, tag) : sprites collidables, calque le plus haut d'abord
    for s in sorted(scene.sprites, key=lambda s: -s["couche"]):
        px, dx, dy = s["pixels"], x - s["x"], y - s["y"]
        if _collidable(s) and 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] and px[dy, dx] >= 0:
            if tag is None or tag in s.get("tags", ()):
                return s
    return None


def _etat(scene):
    if hasattr(scene, "_m0r0"):
        return scene._m0r0
    mur = scene.par_tag("wahtyt")
    sig = (scene.vue, tuple((m["x"], m["y"], m["pixels"].tobytes()) for m in mur))
    clic = [i for i, s in enumerate(scene.sprites) if "sys_click" in s.get("tags", ())]
    if sig not in _DEPARTS:
        _DEPARTS[sig] = {i: (scene.sprites[i]["x"], scene.sprites[i]["y"]) for i in clic}
    sel = [s for s in scene.sprites if _nom(s) == "mosdlc" and _couleur(s) == 11]
    jum = [s for s in scene.sprites if _nom(s) in JUMEAUX]
    fus = {_nom(s) for s in jum if not s.get("bloquant", True)}
    mode_jumeaux = not any(_couleur(s) == 1 for s in jum)
    scene._m0r0 = {"departs": _DEPARTS[sig], "sel": sel[0] if sel else None, "jumeaux": mode_jumeaux, "fus": fus}
    return scene._m0r0


def _portes(scene, st):
    actifs = [s for s in scene.sprites if _nom(s) in JUMEAUX and _nom(s) not in st["fus"]]
    for c in COULEURS:
        plaques = [s for s in scene.sprites if _nom(s) == f"unobxw-{c}"]
        portes = [s for s in scene.sprites if _nom(s) == f"gayktr-{c}"]
        if not plaques or not portes:
            continue
        ouvert = any(j["x"] == p["x"] and j["y"] == p["y"] for p in plaques for j in actifs)
        for p in portes:
            scene.montrer(p, not ouvert)


def _bouger_jumeau(scene, s, dx, dy):
    h, w = scene.vue
    nx, ny = s["x"] + dx, s["y"] + dy
    if nx < 0 or nx >= w or ny < 0 or ny >= h:
        return
    scene.deplacer(s, dx, dy)
    obst = scene.par_tag("wahtyt") + scene.par_tag("xbso") + \
        [o for o in scene.sprites if _nom(o) in {f"gayktr-{c}" for c in COULEURS}]
    if any(_collision(s, o) for o in obst):
        scene.deplacer(s, -dx, -dy)


def step(scene, action):
    st = _etat(scene)
    nom, r, c = action
    h, w = scene.vue
    jum = {_nom(s): s for s in scene.sprites if _nom(s) in JUMEAUX}
    if nom == "CLICK":
        k = min(64 // w, 64 // h)
        px, py = (64 - w * k) // 2, (64 - h * k) // 2
        gx = (c - px) // k if c - px >= 0 else -1
        gy = (r - py) // k if r - py >= 0 else -1
        if not (0 <= gx < w and 0 <= gy < h):
            return
        cible = _sprite_a(scene, gx, gy, "sys_click")
        if cible is not None and _nom(cible) == "mosdlc":
            st["jumeaux"] = False
            for n, s in jum.items():
                if n not in st["fus"]:
                    _repeindre(scene, s, 1)
            if st["sel"] is not None:
                _repeindre(scene, st["sel"], 9)
            st["sel"] = cible
            _repeindre(scene, cible, 11)
        else:
            st["jumeaux"] = True
            for n, s in jum.items():
                if n not in st["fus"]:
                    _repeindre(scene, s, 10)
            if st["sel"] is not None:
                _repeindre(scene, st["sel"], 9)
                st["sel"] = None
        return
    if nom not in VECT:
        return
    dx, dy = VECT[nom]
    if st["sel"] is not None and not st["jumeaux"]:
        b = st["sel"]
        if not (0 <= b["x"] + dx < w and 0 <= b["y"] + dy < h):
            return
        scene.deplacer(b, dx, dy)
        if any(_collision(b, o) for o in scene.sprites):
            scene.deplacer(b, -dx, -dy)
        _portes(scene, st)
        return
    if not st["jumeaux"]:
        return
    actifs = [(n, jum[n]) for n in JUMEAUX if n in jum and n not in st["fus"]]
    avant = {n: (s["x"], s["y"]) for n, s in actifs}
    for n, s in actifs:
        mx, my = MIROIR[n]
        if dx * mx or dy * my:
            _bouger_jumeau(scene, s, dx * mx, dy * my)
    pieges = [s for n, s in actifs if _sprite_a(scene, s["x"], s["y"], "spswjz") is not None]
    if pieges:
        for s in pieges:
            _repeindre(scene, s, 10)
        for i, (x, y) in st["departs"].items():
            scene.placer(scene.sprites[i], x, y)
        return
    vivants = [(n, s) for n, s in actifs if s["visible"]]
    for i, (n1, s1) in enumerate(vivants):
        for n2, s2 in vivants[i + 1:]:
            (x1, y1), (x2, y2) = avant[n1], avant[n2]
            if abs(x1 - x2) == 1 and y1 == y2 and ((s1["x"], s1["y"]) == (x2, y2) or (s2["x"], s2["y"]) == (x1, y1)):
                mx, my = (s1["x"] + s2["x"]) // 2, (s1["y"] + s2["y"]) // 2
                scene.placer(s1, mx, my)
                scene.placer(s2, mx, my)
    cases = {}
    for n, s in vivants:
        cases.setdefault((s["x"], s["y"]), []).append((n, s))
    for lst in cases.values():
        if len(lst) >= 2:
            for n, s in lst[:2]:
                st["fus"].add(n)
                _INTANG.add(id(s))
            for n, s in lst[2:]:
                scene.placer(s, *avant[n])
    _portes(scene, st)
    if not any(n not in st["fus"] for n, _ in actifs):
        scene.niveau_suivant()
