"""T3.1 — ls20 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
État privé (non visible sans HUD) : jauge, vies, direction des rails, objets ramassés/franchis (pour la remise à zéro).
Les constantes viennent de la description ls20.md (jauge 42, cran par niveau, masques et cycle de la clé)."""
import numpy as np

JOUEUR, MUR, PORTE, MODELE, CADRE_PORTE, INDICE_PORTE = "sfqyzhzkij", "ihdgageizm", "rjlbuycveu", "kvynsvxbpi", "vjotnebuqo", "hoswmpiqkw"
CLE, INDICE_CLE, RECHARGE, POUSSOIR, RAIL = "wgmbtyhvbc", "ghizzeqtoh", "npxgalaybz", "gbvqrjtaqo", "xfmluydglp"
RETIRABLES = {"rjlbuycveu", "kvynsvxbpi", "npxgalaybz"}
M_FORME, M_COULEUR, M_ROT = "ttfwljgohq", "soyhouuebz", "rhsxkxzdjz"
MASQUES = [[[0, 0, -1], [-1, 0, 0], [0, -1, 0]], [[-1, 0, -1], [-1, 0, -1], [0, 0, 0]], [[0, -1, 0], [0, -1, 0], [0, 0, 0]],
           [[-1, 0, 0], [0, -1, 0], [-1, 0, -1]], [[-1, 0, -1], [0, 0, -1], [-1, 0, 0]], [[0, 0, 0], [-1, -1, 0], [0, -1, 0]]]
COULEURS = [12, 9, 14, 8]
JAUGE = 42
NIVEAUX = {((35, 11),): 1, ((15, 41),): 2, ((55, 51),): 3, ((10, 6),): 4, ((55, 6),): 5, ((55, 36), (55, 51)): 6, ((30, 51),): 7}
CRAN = {1: 1, 4: 1, 6: 1}
DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]
ST = {}


def _rot(m, q):
    return np.rot90(np.asarray(m), -q)


def _attributs(cle):
    """(forme, couleur, rotation) lus sur les pixels de la clé (échelle 2)."""
    p = cle["pixels"][::2, ::2]
    c = int(p[p >= 0][0])
    for k, m in enumerate(MASQUES):
        for q in range(4):
            if np.array_equal(_rot(m, q) >= 0, p >= 0):
                return k, c, q
    raise ValueError("clé inconnue")


def _boite(a, b):
    ha, wa = a["pixels"].shape
    hb, wb = b["pixels"].shape
    return not (a["x"] >= b["x"] + wb or a["x"] + wa <= b["x"] or a["y"] >= b["y"] + hb or a["y"] + ha <= b["y"])


def _chevauche_pixel(a, b):
    if not _boite(a, b):
        return False
    x0, x1 = max(a["x"], b["x"]), min(a["x"] + a["pixels"].shape[1], b["x"] + b["pixels"].shape[1])
    y0, y1 = max(a["y"], b["y"]), min(a["y"] + a["pixels"].shape[0], b["y"] + b["pixels"].shape[0])
    ra = a["pixels"][y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]]
    rb = b["pixels"][y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra != -1) & (rb != -1)))


def _presents(scene, tag):
    """Recharges, portes et modèles « retirés » sont cachés (Scene.retirer plante sur deux sprites de même nom)."""
    return [s for s in scene.par_tag(tag) if s["visible"]]


def _a_origine(scene, x, y, tag):
    for s in sorted(scene.sprites, key=lambda s: -s["couche"]):
        if tag in s.get("tags", ()) and s["x"] == x and s["y"] == y and (s["visible"] or tag not in RETIRABLES):
            return s
    return None


def _init(scene, sig):
    j = scene.par_tag(JOUEUR)[0]
    rails = []
    for ri, r in enumerate(scene.par_tag(RAIL)):
        for tag in (M_FORME, M_COULEUR, M_ROT):
            for mi, m in enumerate(scene.par_tag(tag)):
                if _chevauche_pixel(r, m):
                    rails.append({"ri": ri, "tag": tag, "mi": mi, "x0": m["x"], "y0": m["y"], "dir": 0, "undo": None})
    niv = NIVEAUX.get(tuple(sorted((m["x"], m["y"]) for m in scene.par_tag(MODELE))), 0)
    ST.clear()
    ST.update(sig=sig, niv=niv, cran=CRAN.get(niv, 2), jauge=JAUGE, vies=3, depart=(j["x"], j["y"]),
              cle0=scene.par_tag(CLE)[0]["pixels"].copy(), rails=rails, retires=[[], [], []],
              obstacles={(s["x"], s["y"]) for s in scene.par_tag(MUR) + scene.par_tag(PORTE)},
              nportes=len(_presents(scene, PORTE)), nrech=len(_presents(scene, RECHARGE)), scene=id(scene))


def _est_initiale(scene):
    j = scene.par_tag(JOUEUR)[0]
    return ((j["x"], j["y"]) == ST["depart"] and np.array_equal(scene.par_tag(CLE)[0]["pixels"], ST["cle0"])
            and len(_presents(scene, PORTE)) == ST["nportes"] and len(_presents(scene, RECHARGE)) == ST["nrech"])


def _conforme(scene, porte):
    m = _a_origine(scene, porte["x"] + 1, porte["y"] + 1, MODELE)
    return m is not None and np.array_equal(scene.par_tag(CLE)[0]["pixels"][::2, ::2], m["pixels"])


def _indice(scene):
    """Niveau 1 : la clé devient conforme à une porte restante → indice (fini à la fin du coup) ; vrai si oui."""
    return ST["niv"] == 1 and any(_conforme(scene, p) for p in _presents(scene, PORTE))


def _ecrire_cle(scene, cle, px):
    for dy in range(px.shape[0]):
        for dx in range(px.shape[1]):
            scene.ecrire(cle, dy, dx, int(px[dy, dx]))


def _case(scene, x, y):
    j = scene.par_tag(JOUEUR)[0]
    h, w = j["pixels"].shape
    bloque = recharge = pause = False
    for s in [s for s in scene.sprites if x <= s["x"] < x + w and y <= s["y"] < y + h]:
        t = s.get("tags", ())
        if not s["visible"] and RETIRABLES & set(t):
            continue
        cle = scene.par_tag(CLE)[0]
        if MUR in t:
            bloque = True
            break
        elif PORTE in t:
            if not _conforme(scene, s):
                bloque = pause = True
        elif RECHARGE in t:
            recharge = True
            ST["jauge"] = JAUGE
            ST["retires"][0].append(s)
            scene.montrer(s, False)
        elif M_FORME in t:
            k, c, q = _attributs(cle)
            px = np.where(_rot(MASQUES[(k + 1) % 6], q) == 0, c, -1)
            _ecrire_cle(scene, cle, np.repeat(np.repeat(px, 2, 0), 2, 1))
            pause = pause or _indice(scene)
        elif M_COULEUR in t:
            c = _attributs(cle)[1]
            scene.recolorer(cle, c, COULEURS[(COULEURS.index(c) + 1) % 4])
            pause = pause or _indice(scene)
        elif M_ROT in t:
            scene.tourner(cle, 1)
            pause = pause or _indice(scene)
    return bloque, recharge, pause


def _rails(scene, annuler=False):
    for e in ST["rails"]:
        m = scene.par_tag(e["tag"])[e["mi"]]
        if annuler:
            if e["undo"] is not None:
                scene.placer(m, e["undo"][0], e["undo"][1])
                e["dir"] = e["undo"][2]
                e["undo"] = None
            continue
        r = scene.par_tag(RAIL)[e["ri"]]
        d0, ok = e["dir"], False
        for d in (d0, (d0 - 1) % 4, (d0 + 1) % 4, (d0 + 2) % 4):
            nx, ny = m["x"] + DIRS[d][0] * 5, m["y"] + DIRS[d][1] * 5
            rx, ry = nx - r["x"], ny - r["y"]
            if 0 <= ry < r["pixels"].shape[0] and 0 <= rx < r["pixels"].shape[1] and r["pixels"][ry, rx] >= 0:
                e["undo"] = (m["x"], m["y"], d0)
                e["dir"] = d
                scene.placer(m, nx, ny)
                ok = True
                break
        if not ok:
            e["undo"] = None


def _jauge():
    if ST["jauge"] >= 0:
        ST["jauge"] -= ST["cran"]
    return ST["jauge"] >= 0


def _poussoir(scene, j):
    for p in scene.par_tag(POUSSOIR):
        if not (p.get("bloquant", True) and j.get("bloquant", True) and _boite(p, j)):
            continue
        dx, dy = {"t": (0, -1), "b": (0, 1), "r": (1, 0), "l": (-1, 0)}.get(p.get("nom", " ")[-1], (0, 0))
        h, w = p["pixels"].shape
        n = None
        for k in range(1, 12):
            if (p["x"] + dx + dx * w * k, p["y"] + dy + dy * h * k) in ST["obstacles"]:
                n = k
                break
        if n is None or n - 1 <= 0:
            continue
        scene.deplacer(j, dx * w * (n - 1), dy * h * (n - 1))
        _case(scene, j["x"], j["y"])
        return True
    return False


def _victoire(scene, j):
    for p in _presents(scene, PORTE):
        if (j["x"], j["y"]) == (p["x"], p["y"]) and _conforme(scene, p):
            m = _a_origine(scene, p["x"] + 1, p["y"] + 1, MODELE)
            ST["retires"][1].append(p)
            ST["retires"][2].append(m)
            scene.montrer(p, False)
            scene.montrer(m, False)
            c = _a_origine(scene, p["x"] - 1, p["y"] - 1, CADRE_PORTE)
            if c is not None and "vfkkzdgxzx" in c.get("tags", ()):
                scene.montrer(c, False)
                i = _a_origine(scene, p["x"] - 1, p["y"] - 1, INDICE_PORTE)
                if i is not None:
                    scene.montrer(i, False)
                for s in scene.par_tag(INDICE_CLE):
                    scene.montrer(s, False)
    return not _presents(scene, PORTE)


def _mort(scene, j):
    ST["vies"] -= 1
    if ST["vies"] == 0:
        scene.perdre()
        return
    scene.placer(j, *ST["depart"])
    _ecrire_cle(scene, scene.par_tag(CLE)[0], ST["cle0"])
    for groupe in ST["retires"]:
        for s in groupe:
            scene.montrer(s, True)
    ST["retires"] = [[], [], []]
    ST["jauge"] = JAUGE
    for s in scene.par_tag(INDICE_CLE) + scene.par_tag(INDICE_PORTE):
        scene.montrer(s, False)
    for s in scene.par_tag(CADRE_PORTE):
        scene.montrer(s, True)
    for e in ST["rails"]:
        m = scene.par_tag(e["tag"])[e["mi"]]
        scene.placer(m, e["x0"], e["y0"])
        e["dir"], e["undo"] = 0, None


def step(scene, action):
    sig = tuple(sorted((s["x"], s["y"]) for s in scene.par_tag(MUR)))
    if ST.get("sig") != sig or (ST.get("scene") != id(scene) and _est_initiale(scene)):
        _init(scene, sig)
    ST["scene"] = id(scene)
    vec = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}.get(action[0])
    if vec is None:
        return
    j = scene.par_tag(JOUEUR)[0]
    h, w = j["pixels"].shape
    _rails(scene)
    tx, ty = j["x"] + vec[0] * w, j["y"] + vec[1] * h
    bloque, recharge, pause = _case(scene, tx, ty)
    if not bloque:
        scene.placer(j, tx, ty)
    else:
        _rails(scene, annuler=True)
    if pause:
        return
    epuise = not recharge and not _jauge()
    if not epuise and _poussoir(scene, j):
        return
    if _victoire(scene, j):
        scene.niveau_suivant()
        return
    if epuise:
        _mort(scene, j)
