"""T3.1 — dc22 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Mode d'interaction d'un sprite lu sur (visible, bloquant) : mur (V,B), sol (V,-), invisible-bloquant (-,B), retiré (-,-).
`bloquant` est un attribut privé du sprite (non rendu), tenu à jour ici. Grue et cycle de couleur (niv. 4-5) non modélisés.
Chute après un clic : le moteur rejoue l'état d'avant le clic (hors HUD) → on restaure l'instantané."""
import numpy as np

JOUEUR, BUT, BOUTON, CLIC, CLE, IGNORE, INDIC = "jfva", "goknoi", "buezna", "sys_click", "piyqze", "ignore", "njvd-rolo"
PAS = 2


def _lettre(s):
    return next((t for t in s.get("tags", ()) if len(t) == 1), None)


def _retire(s):
    return not s["visible"] and not s["bloquant"]


def _mode(scene, s, visible, bloquant):
    scene.montrer(s, visible)
    s["bloquant"] = bloquant


def _activer(scene, s):
    t = s.get("tags", ())
    if "omvz" in t or BOUTON in t:
        _mode(scene, s, True, False)
    elif "inzejtible" in t:
        _mode(scene, s, False, True)
    else:
        _mode(scene, s, True, True)


def _joueur(scene):
    return scene.par_tag(JOUEUR)[0]


def _px(s, x, y):
    p, dx, dy = s["pixels"], x - s["x"], y - s["y"]
    if 0 <= dy < p.shape[0] and 0 <= dx < p.shape[1]:
        return int(p[dy, dx])
    return None


def _collision(a, b):
    """collides_with : deux sprites bloquants dont des pixels >= 0 se chevauchent."""
    ha, wa = a["pixels"].shape
    hb, wb = b["pixels"].shape
    if a["x"] >= b["x"] + wb or a["x"] + wa <= b["x"] or a["y"] >= b["y"] + hb or a["y"] + ha <= b["y"]:
        return False
    x0, x1 = max(a["x"], b["x"]), min(a["x"] + wa, b["x"] + wb)
    y0, y1 = max(a["y"], b["y"]), min(a["y"] + ha, b["y"] + hb)
    ra = a["pixels"][y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]]
    rb = b["pixels"][y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra >= 0) & (rb >= 0)))


def _sol(scene, j):
    """sxnzvaqltp : un sprite « sol » (visible, non bloquant) a un pixel >= 0 sous le coin haut-gauche du joueur."""
    for s in scene.sprites:
        t = s.get("tags", ())
        if s is j or IGNORE in t or "crzsjq" in t or "vcha" in t:
            continue
        if s["visible"] and not s["bloquant"]:
            v = _px(s, j["x"], j["y"])
            if v is not None and v >= 0:
                return True
    return False


def _cle_touchee(scene, j):
    """yhthylsyvr(tag clé) : pixel fantôme (-2) d'une clé non retirée, ou pixel >= 0 d'une clé bloquante, sous le joueur 2x2."""
    for s in scene.sprites:
        if s is j or IGNORE in s.get("tags", ()) or CLE not in s.get("tags", ()):
            continue
        for dx in range(2):
            for dy in range(2):
                v = _px(s, j["x"] + dx, j["y"] + dy)
                if v is None or v == -1:
                    continue
                if (v == -2 and not _retire(s)) or (v >= 0 and s["bloquant"]):
                    return s
    return None


def _indicateurs(scene, j):
    """yuonzbouxb : boutons de lettre L visibles tant que le joueur chevauche un indicateur de lettre L."""
    ind = [s for s in scene.sprites if INDIC in s.get("tags", ()) and _lettre(s)]
    if not ind:
        return
    actives = set()
    for s in ind:
        if not _retire(s) and _chevauche(j, s):
            actives.add(_lettre(s))
    lettres = {_lettre(s) for s in ind}
    for b in scene.par_tag(BOUTON):
        L = _lettre(b)
        if L in lettres:
            _mode(scene, b, L in actives, False)


def _chevauche(a, b):
    ha, wa = a["pixels"].shape
    hb, wb = b["pixels"].shape
    if a["x"] >= b["x"] + wb or a["x"] + wa <= b["x"] or a["y"] >= b["y"] + hb or a["y"] + ha <= b["y"]:
        return False
    x0, x1 = max(a["x"], b["x"]), min(a["x"] + wa, b["x"] + wb)
    y0, y1 = max(a["y"], b["y"]), min(a["y"] + ha, b["y"] + hb)
    ra = a["pixels"][y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]]
    rb = b["pixels"][y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra > -1) & (rb > -1)))


def _etats(scene):
    """Nombre d'états par préfixe : plus grand chiffre final parmi les sprites « tovemc » de ce préfixe."""
    n = {}
    for s in scene.sprites:
        nom = s.get("nom", "")
        if nom and nom[-1].isdigit() and "tovemc" in s.get("tags", ()):
            n[nom[:-1]] = max(n.get(nom[:-1], 0), int(nom[-1]))
    return n


def _suivant(nom, n):
    if not nom or not nom[-1].isdigit():
        return ""
    k = n.get(nom[:-1], 0)
    if k <= 1:
        return ""
    return nom[:-1] + str(int(nom[-1]) % k + 1)


def _a_place(scene, x, y, nom):
    repli = None
    for s in scene.sprites:
        if s["x"] == x and s["y"] == y and s.get("nom") == nom:
            if not _retire(s):
                return s
            if repli is None:
                repli = s
    return repli


def _clic_sur(scene, x, y, tag):
    """xodizggcom : sprite visible du tag, pixel >= 0 en (x, y), calque le plus haut d'abord."""
    for s in sorted(scene.sprites, key=lambda s: -s["couche"]):
        t = s.get("tags", ())
        if IGNORE in t or tag not in t or not s["visible"]:
            continue
        v = _px(s, x, y)
        if v is not None and v >= 0:
            return s
    return None


def _instantane(scene):
    return [(s, s["x"], s["y"], s["visible"], s["bloquant"]) for s in scene.sprites]


def _restaurer(scene, inst):
    for s, x, y, v, b in inst:
        scene.placer(s, x, y)
        _mode(scene, s, v, b)


def _clic(scene, row, col):
    h, w = scene.vue
    k = min(64 // w, 64 // h)
    gx, gy = (64 - w * k) // 2, (64 - h * k) // 2
    x = (col - gx) // k if col - gx >= 0 else -1
    y = (row - gy) // k if row - gy >= 0 else -1
    if x < 0 or y < 0 or x >= w or y >= h:
        return
    x, y = x + scene.camera[0], y + scene.camera[1]
    j = _joueur(scene)
    inst = _instantane(scene)
    b = _clic_sur(scene, x, y, BOUTON)
    if b is not None:
        L = _lettre(b)
        if L is not None:
            for s in scene.par_tag("aybe"):
                scene.placer(s, 500, s["y"])
            groupe = [s for s in scene.sprites if L in s.get("tags", ()) and s is not b and s["visible"]]
            n = _etats(scene)
            pad = next((s for s in groupe if "tewfut" in s.get("tags", ()) and (s["x"], s["y"]) == (j["x"], j["y"])), None)
            if pad is not None:
                cible_nom = _suivant(pad.get("nom"), n)
                cible = next((s for s in groupe if s is not pad and "tewfut" in s.get("tags", ()) and cible_nom
                              and s.get("nom") == cible_nom), None)
                if cible is None:
                    cible = next((s for s in groupe if s is not pad and "tewfut" in s.get("tags", ())
                                  and s.get("nom") == pad.get("nom")), None)
                if cible is not None:
                    scene.placer(j, cible["x"], cible["y"])
            for s in groupe:
                nom2 = _suivant(s.get("nom"), n)
                if nom2:
                    s2 = _a_place(scene, s["x"], s["y"], nom2)
                    if s2 is not None:
                        _mode(scene, s, False, False)
                        _activer(scene, s2)
    if _clic_sur(scene, x, y, CLIC) is not None and not _sol(scene, j):
        _restaurer(scene, inst)  # chute : retour à l'état d'avant le clic


def step(scene, action):
    nom, row, col = action
    j = _joueur(scene)
    _indicateurs(scene, j)
    if nom == "CLICK":
        _clic(scene, row, col)
        _indicateurs(scene, j)
        return
    d = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}.get(nom)
    if d is None:
        return
    x0, y0 = j["x"], j["y"]
    scene.deplacer(j, d[0] * PAS, d[1] * PAS)
    bloque = any(s is not j and IGNORE not in s.get("tags", ()) and s["bloquant"] and _collision(j, s)
                 for s in scene.sprites)
    if bloque or not _sol(scene, j):
        scene.placer(j, x0, y0)
    c = _cle_touchee(scene, j)
    if c is not None:
        L = _lettre(c)
        if L:
            boutons = [b for b in scene.par_tag(BOUTON) if L in b.get("tags", ())]
            for b in boutons:
                _mode(scene, b, True, False)
            if boutons:
                _mode(scene, c, False, False)
    _indicateurs(scene, j)
    but = scene.par_tag(BUT)
    if but and (j["x"], j["y"]) == (but[0]["x"], but[0]["y"]):
        scene.niveau_suivant()
