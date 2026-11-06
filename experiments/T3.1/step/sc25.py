"""T3.1 — sc25 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
État privé : compteur de coups (la jauge n'en montre qu'une image arrondie), sort-indice sélectionné, regard (dernière
flèche, conservé d'un niveau à l'autre), démonstration initiale du niveau 1, index de la petite cible de téléportation.
Constantes tirées de sc25.md / du source (max par niveau, motifs, couleurs, départs)."""
import numpy as np

NIV = {"duvwsv-2": 1, "duvwsv-1": 2, "duvwsv-4": 3, "duvwsv-5": 4, "duvwsv-6": 5, "duvwsv-13": 6}
MAXI = {1: 50, 2: 25, 3: 50, 4: 35, 5: 65, 6: 60}
TOUS = ["fibcey", "tevyeq", "sieesc_chwjgc"]
SORTS = {1: ["sieesc_chwjgc"], 2: ["tevyeq"], 3: ["fibcey"], 4: ["fibcey", "sieesc_chwjgc"], 5: TOUS, 6: TOUS}
MOTIFS = {"tevyeq": {(0, 0), (0, 1), (1, 1)}, "sieesc_chwjgc": {(0, 1), (1, 0), (1, 2), (2, 1)},
          "fibcey": {(0, 1), (1, 1), (2, 1)}}  # ordre = ordre de reconnaissance du jeu
COUL = {"tevyeq": 11, "sieesc_chwjgc": 15, "fibcey": 6}
DEPART = {1: (39, 19), 2: (31, 35), 3: (35, 22), 4: (35, 19), 5: (35, 15), 6: (41, 21)}
BASE = np.array([[10, 10], [9, 9]])
ROT = {0: 180, 1: 0, 2: 90, 3: 270}  # regard -> rotation (horaire) du joueur
DIRS = {"UP": (0, 0, -1), "DOWN": (1, 0, 1), "LEFT": (2, -1, 0), "RIGHT": (3, 1, 0)}
CASE, ZONE, JAUGE = "clzbxlm-sptivk-slsrhr", "clcbko", "action-ui"
MURS_GRANDIR = ("dosorb", "seofsw-dosorb", "crzdcq")
CIBLES_FEU = ("dosorb", "seofsw-dosorb", "crzdcq", "tagsmh", "seofsw-tagsmh")
ST = {"regard": 1}


# ------------------------------------------------------------------ lecture de la scène
def _gone(scene):
    if not hasattr(scene, "_sc25_gone"):
        scene._sc25_gone = set()
    return scene._sc25_gone


def _vivants(scene):
    g = _gone(scene)
    return [s for s in scene.sprites if id(s) not in g]


def _nom(scene, nom):
    return [s for s in _vivants(scene) if s.get("nom") == nom]


def _cacher(scene, s):
    scene.montrer(s, False)
    _gone(scene).add(id(s))


def _joueur(scene):
    return _nom(scene, "pluyoo")[0]


def _echelle(j):
    return j["pixels"].shape[0] // 2


def _rotation(j):
    p = j["pixels"][::_echelle(j), ::_echelle(j)]
    if p[1, 0] == 9 and p[1, 1] == 9:
        return 0
    if p[0, 0] == 9 and p[0, 1] == 9:
        return 180
    if p[0, 0] == 9 and p[1, 0] == 9:
        return 90
    return 270


def _niveau(scene):
    for s in scene.sprites:
        if s.get("nom") in NIV:
            return NIV[s["nom"]]
    return 0


def _vides(scene):
    g = _nom(scene, JAUGE)[0]["pixels"]
    return int((g[:, 0] == 0).sum()) // 2


def _cases(scene):
    out = {}
    for s in _nom(scene, CASE):
        out[((s["y"] - 49) // 5, (s["x"] - 24) // 5)] = s
    return out


def _etat(scene):
    if getattr(scene, "_sc25", None) is not None:
        return scene._sc25
    niv, e = _niveau(scene), _vides(scene)
    mx = MAXI.get(niv, 50)
    cases = _cases(scene)
    allumees = {rc for rc, s in cases.items() if int(s["pixels"][0, 0]) in (14, 11, 15, 6)}
    zeros = {rc for rc, s in cases.items() if int(s["pixels"][0, 0]) == 0}
    j = _joueur(scene)
    initial = (e == 0 and not allumees and (j["x"], j["y"]) == DEPART.get(niv) and _echelle(j) == 2)
    nouveau = ST.get("niv") != niv or (initial and ST.get("n", 0) > 0) or (initial and ST.get("mod", False))
    if nouveau:
        n, premier = 0, niv == 1
        hint = SORTS[niv][0] if niv <= 3 else None
        petit = 0
    else:
        n, premier, hint, petit = ST.get("n", 0), ST.get("premier", False), ST.get("hint"), ST.get("petit", 0)
    if n * 32 // mx != e:  # resynchronisation : n le plus proche compatible avec la jauge
        cands = [k for k in range(0, mx + 1) if k * 32 // mx == e]
        n = min(cands, key=lambda k: abs(k - n)) if cands else n
    cands = [None] + list(MOTIFS)
    cands = [h for h in cands if (MOTIFS[h] - allumees if h else set()) == zeros]
    if hint not in cands and cands:
        hint = cands[0]
    st = {"niv": niv, "mx": mx, "n": n, "premier": premier, "hint": hint, "petit": petit,
          "allumees": allumees, "mod": False}
    scene._sc25 = st
    return st


def _sauver(scene, st):
    ST.update({k: st[k] for k in ("niv", "n", "premier", "hint", "petit", "mod")})


# ------------------------------------------------------------------ collisions
def _chevauche(a, b):
    ha, wa = a["pixels"].shape
    hb, wb = b["pixels"].shape
    if a["x"] >= b["x"] + wb or a["x"] + wa <= b["x"] or a["y"] >= b["y"] + hb or a["y"] + ha <= b["y"]:
        return False
    x0, x1 = max(a["x"], b["x"]), min(a["x"] + wa, b["x"] + wb)
    y0, y1 = max(a["y"], b["y"]), min(a["y"] + ha, b["y"] + hb)
    ra = a["pixels"][y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]]
    rb = b["pixels"][y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra != -1) & (rb != -1)))


def _essai(scene, j, dx, dy):
    scene.deplacer(j, dx, dy)
    coll = [s for s in _vivants(scene) if s is not j and s.get("bloquant", True) and _chevauche(j, s)]
    if coll:
        scene.deplacer(j, -dx, -dy)
    return coll


def _pixel(s, x, y):
    p = s["pixels"]
    dx, dy = x - s["x"], y - s["y"]
    return 0 <= dy < p.shape[0] and 0 <= dx < p.shape[1] and p[dy, dx] != -1


def _boite(s, x, y, w=None, h=None):
    hh, ww = s["pixels"].shape
    w, h = w or ww, h or hh
    return s["x"] <= x < s["x"] + w and s["y"] <= y < s["y"] + h


# ------------------------------------------------------------------ effets composés
def _remplacer_joueur(scene, j, pix, x, y):
    """Changement d'échelle : nouveau sprite joueur (creer) ; l'ancien est caché. Les sprites suivants du même calque
    sont recréés pour garder l'ordre d'affichage."""
    g = _gone(scene)
    i = next(k for k, s in enumerate(scene.sprites) if s is j)
    suivants = [s for s in scene.sprites[i + 1:] if s["couche"] == j["couche"] and id(s) not in g]
    n = scene.creer(dict(j, pixels=np.asarray(pix, dtype=np.int16)), x, y)
    _cacher(scene, j)
    for s in suivants:
        vis = s["visible"]
        c = scene.creer(s, s["x"], s["y"])
        scene.montrer(c, vis)
        _cacher(scene, s)
    return n


def _bonus(scene, st, j, taille):
    for b in _nom(scene, "enjehv-pahtoz"):
        if j["x"] < b["x"] + 2 and j["x"] + taille > b["x"] and j["y"] < b["y"] + 2 and j["y"] + taille > b["y"]:
            st["n"] = max(0, st["n"] - 10)
            _cacher(scene, b)
            return


def _marqueurs(scene, echelle):
    for m in _nom(scene, "acyylh-tevyeq-inkpfx"):
        scene.montrer(m, echelle == 2)
    for m in _nom(scene, "smzaik-tevyeq-inkpfx"):
        scene.montrer(m, echelle == 1)


def _bloque_grand(scene, j, x, y):
    for dy in range(4):
        for dx in range(4):
            px, py = x + dx, y + dy
            if px < 0 or py < 0 or px >= 64 or py >= 64:
                return True
            for s in _vivants(scene):
                if s is j or not s.get("bloquant", True):
                    continue
                nom = s.get("nom", "")
                if nom.startswith("duvwsv-") or nom == "crzdcq":
                    if _pixel(s, px, py):
                        return True
                elif nom in ("dosorb", "seofsw-dosorb"):
                    if _boite(s, px, py, 4, 3):  # le jeu teste les pixels bruts (non tournés) : 4×3
                        return True
    return False


def _sort(scene, st, sp):
    st["hint"] = None
    j = _joueur(scene)
    ech = _echelle(j)
    if sp == "tevyeq":
        grands = _nom(scene, "tevyeq-tagsmh")
        cibles = grands if ech == 2 else _nom(scene, "smzaik-tevyeq-tagsmh")
        if cibles:
            mq = _nom(scene, "acyylh-tevyeq-inkpfx")
            if ech == 2:
                idx = 0
                if mq:
                    for k, c in enumerate(cibles):
                        if (c["x"] - 1, c["y"] - 1) == (mq[0]["x"], mq[0]["y"]):
                            idx = k
            else:
                idx = st["petit"] % len(cibles)
            scene.placer(j, cibles[idx]["x"], cibles[idx]["y"])
            if ech == 2:
                gi = (idx + 1) % len(cibles)
            else:
                st["petit"] = (idx + 1) % len(cibles)
                gi = None
            if mq and grands:
                if gi is None:
                    gi = 0
                    for k, c in enumerate(grands):
                        if (c["x"] - 1, c["y"] - 1) == (mq[0]["x"], mq[0]["y"]):
                            gi = k
                scene.placer(mq[0], grands[gi]["x"] - 1, grands[gi]["y"] - 1)
    elif sp == "sieesc_chwjgc":
        if ech == 1:
            off = None
            for ox in range(-2, 1):
                for oy in range(-2, 1):
                    if not _bloque_grand(scene, j, j["x"] + ox, j["y"] + oy):
                        off = (ox, oy)
                        break
                if off:
                    break
            if off is not None:
                pix = np.repeat(np.repeat(j["pixels"], 2, 0), 2, 1)
                n = _remplacer_joueur(scene, j, pix, j["x"] + off[0], j["y"] + off[1])
                _bonus(scene, st, n, 4)
                _marqueurs(scene, 2)
        else:
            n = _remplacer_joueur(scene, j, j["pixels"][::2, ::2], j["x"], j["y"])
            _bonus(scene, st, n, 2)
            _marqueurs(scene, 1)
    elif sp == "fibcey":
        vx, vy = [(0, -1), (0, 1), (-1, 0), (1, 0)][ST["regard"]]
        t = 2 * ech
        ox = t - 1 if vx > 0 else 0
        oy = t - 1 if vy > 0 else 0
        touche = None
        for i in range(1, 64):
            px, py = j["x"] + ox + vx * i, j["y"] + oy + vy * i
            if not (0 <= px < 64 and 0 <= py < 64):
                break
            for s in _vivants(scene):
                nom = s.get("nom", "")
                if nom in CIBLES_FEU:
                    if _boite(s, px, py):
                        touche = s
                        break
                elif nom.startswith("duvwsv-") and _pixel(s, px, py):
                    touche = s
                    break
            if touche is not None:
                break
        if touche is not None and touche["nom"] in ("tagsmh", "seofsw-tagsmh"):
            portes = "dosorb" if touche["nom"] == "tagsmh" else "seofsw-dosorb"
            _cacher(scene, touche)
            for p in _nom(scene, portes):
                _cacher(scene, p)
    st["allumees"] = set()
    st["n"] += 1


def _reconnu(allumees, niv):
    for sp, m in MOTIFS.items():
        if m == allumees:
            return sp if sp in SORTS.get(niv, []) else None
    return None


def _peindre(scene, st):
    rec = _reconnu(st["allumees"], st["niv"])
    for rc, s in _cases(scene).items():
        if rc in st["allumees"]:
            c = COUL[rec] if rec else 14
        elif st["hint"] and rc in MOTIFS[st["hint"]]:
            c = 0
        else:
            c = 2
        cur = int(s["pixels"][0, 0])
        if cur != c:
            scene.recolorer(s, cur, c)


def _jauge(scene, st):
    g = _nom(scene, JAUGE)[0]
    e = st["n"] * 32 // st["mx"]
    for r in range(32):
        c = 0 if r < e else 14
        for yy in (2 * r, 2 * r + 1):
            for xx in range(g["pixels"].shape[1]):
                if g["pixels"][yy, xx] != c:
                    scene.ecrire(g, yy, xx, c)


# ------------------------------------------------------------------ actions
def _fleche(scene, st, nom):
    regard, dx, dy = DIRS[nom]
    j = _joueur(scene)
    ech = _echelle(j)
    pas = 2 if ech == 1 else 4
    ST["regard"] = regard
    q = ((ROT[regard] - _rotation(j)) % 360) // 90
    if q:
        scene.tourner(j, q)
    coll = _essai(scene, j, dx * pas, dy * pas)
    if coll and ech == 2:
        coll = _essai(scene, j, dx * pas // 2, dy * pas // 2)
    _bonus(scene, st, j, 2)
    sortie = next((s for s in coll if s.get("nom") == "exydhv"), None)
    if sortie is not None:
        cx, cy = j["x"] + 1, j["y"] + 1
        ex, ey = sortie["x"] + 2, sortie["y"] + 3  # centre des pixels bruts 6×5 (non tournés)
        ddx, ddy = ex - cx, ey - cy
        h = pas // 2
        if abs(ddx) > abs(ddy):
            mv = (h if ddx > 0 else -h, 0)
        else:
            mv = (0, h if ddy > 0 else -h)
        scene.deplacer(j, 2 * mv[0], 2 * mv[1])
        scene.niveau_suivant()
        return
    st["n"] += 1


def _clic(scene, st, y, x):
    hit = None
    for s in sorted(_vivants(scene), key=lambda s: -s["couche"]):
        if s.get("bloquant", True) and _pixel(s, x, y):
            hit = s
            break
    if hit is None:
        return
    nom = hit.get("nom", "")
    if nom == "sptivk-caxiiu" or (nom.startswith("sptivk-") and nom != "sptivk-ui"):
        sp = None
        if nom != "sptivk-caxiiu" and nom != "sptivk-button":
            sp = nom[len("sptivk-"):]
        else:
            for s in _vivants(scene):
                n2 = s.get("nom", "")
                if n2.startswith("sptivk-") and n2 not in ("sptivk-caxiiu", "sptivk-ui"):
                    if abs(s["x"] - hit["x"]) <= 5 and abs(s["y"] - hit["y"]) <= 5:
                        sp = n2[len("sptivk-"):]
                        break
        if sp in MOTIFS and st["hint"] != sp:
            st["hint"] = sp
            _peindre(scene, st)
        return
    if nom == CASE:
        rc = ((hit["y"] - 49) // 5, (hit["x"] - 24) // 5)
    elif ZONE in nom.lower():
        rc = None
        cases = _cases(scene)
        for r in range(3):
            for c in range(3):
                cs = cases.get((r, c))
                if cs is not None and rc is None and _boite(hit, cs["x"] + 1, cs["y"] + 1):
                    rc = (r, c)
        if rc is None:
            return
    else:
        return
    st["allumees"] = st["allumees"] ^ {rc}
    st["n"] += 1
    if st["n"] > st["mx"]:
        scene.perdre()
        _peindre(scene, st)
        return
    sp = _reconnu(st["allumees"], st["niv"])
    if sp:
        _sort(scene, st, sp)
    _peindre(scene, st)


def step(scene, action):
    st = _etat(scene)
    nom, row, col = action
    if st["premier"]:
        st["premier"] = False
        st["mod"] = True
        _sauver(scene, st)
        return
    if nom in DIRS:
        _fleche(scene, st, nom)
    elif nom == "CLICK":
        _clic(scene, st, row, col)
    st["mod"] = True
    _jauge(scene, st)
    _sauver(scene, st)
