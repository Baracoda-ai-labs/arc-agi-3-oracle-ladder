"""T3.1 — cd82 : dynamique du jeu exprimée avec les seuls effets de ontologie_exec.Scene.
État (poste, couleur courante, présence du gobelet) relu dans la scène à chaque coup : pas d'état privé."""
import numpy as np

_ = -1
_H = np.array([[2] + [_] * 12 + [2]] + [[2] + [15] * 12 + [2]] * 7 + [[2] * 14])
_D = np.array([
    [_, _, _, _, _, _, 2, _, _, _, _, _, _, _, _, _, _],
    [_, _, _, _, _, 2, 2, 2, _, _, _, _, _, _, _, _, _],
    [_, _, _, _, 2, 2, 15, 2, 2, _, _, _, _, _, _, _, _],
    [_, _, _, 2, 2, 15, 15, 15, 2, 2, _, _, _, _, _, _, _],
    [_, _, 2, 2, 15, 15, 15, 15, 15, 2, 2, _, _, _, _, _, _],
    [_, 2, 2, 15, 15, 15, 15, 15, 15, 15, 2, 2, _, _, _, _, _],
    [2, 2, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 2, _, _, _, _],
    [_, _, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 2, _, _, _],
    [_, _, _, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 2, _, _],
    [_, _, _, _, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 2, _],
    [_, _, _, _, _, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 2],
    [_, _, _, _, _, _, 15, 15, 15, 15, 15, 15, 15, 15, 2, 2, _],
    [_, _, _, _, _, _, _, 15, 15, 15, 15, 15, 15, 2, 2, _, _],
    [_, _, _, _, _, _, _, _, 15, 15, 15, 15, 2, 2, _, _, _],
    [_, _, _, _, _, _, _, _, _, 15, 15, 2, 2, _, _, _, _],
    [_, _, _, _, _, _, _, _, _, _, 2, 2, _, _, _, _, _],
    [_, _, _, _, _, _, _, _, _, _, 2, _, _, _, _, _, _],
])
_G = np.array([[2, 15, 15, 15, 15, 2]] * 3 + [[2, 2, 0, 0, 2, 2], [_, 2, 2, 2, 2, _]])

POSTES = [("h", 25, 24, 180), ("d", 33, 21, 0), ("h", 38, 32, 270), ("d", 33, 40, 90),
          ("h", 25, 45, 0), ("d", 14, 40, 180), ("h", 17, 32, 90), ("d", 14, 21, 270)]
ANNEAU = {0: (0, 1), 1: (0, 2), 2: (1, 2), 3: (2, 2), 4: (2, 1), 5: (2, 0), 6: (1, 0), 7: (0, 0)}
CASE = {v: k for k, v in ANNEAU.items()}
GOB = {0: ((4, -6), 180), 2: ((10, 4), 270), 4: ((4, 10), 0), 6: ((-6, 4), 90)}


def _nom(scene, prefixe):
    return [s for s in scene.sprites if s.get("nom", "").startswith(prefixe)]


def _etat(scene):
    panier = _nom(scene, "ActiveBasket")[0]
    poste = next(i for i, p in enumerate(POSTES) if (p[1], p[2]) == (panier["x"], panier["y"]))
    ind = _nom(scene, "ydiwkzjkgl")[0]
    past = next(s for s in _nom(scene, "pqkenviek") if (s["x"], s["y"] + 5) == (ind["x"], ind["y"]))
    couleur = int(past["pixels"][2, 2])
    gobelet = len(_nom(scene, "pqkenviek")) >= 7  # niveaux 3-6
    return panier, poste, couleur, gobelet


def _recreer(scene, panier, poste, couleur, gobelet):
    forme, x, y, rot = POSTES[poste]
    scene.retirer(panier)
    n = scene.creer({"nom": "ActiveBasket", "tags": [], "pixels": _H if forme == "h" else _D, "couche": 2,
                     "visible": True, "bloquant": True}, x, y)
    scene.tourner(n, rot // 90)
    scene.recolorer(n, 15, couleur)
    if not gobelet:
        return
    for g in _nom(scene, "ctwspzkygu"):
        scene.retirer(g)
    if poste in GOB:
        (ox, oy), r = GOB[poste]
        g = scene.creer({"nom": "ctwspzkygu", "tags": [], "pixels": _G, "couche": 2, "visible": True, "bloquant": True},
                        x + ox, y + oy)
        scene.tourner(g, r // 90)
        scene.recolorer(g, 15, couleur)


def _peindre(scene, cases, couleur):
    toile = _nom(scene, "xytrjjbyib")[0]
    for dy, dx in cases:
        scene.ecrire(toile, dy, dx, couleur)
    modele = _nom(scene, "eoqnvkspoa-")[0]
    masque = np.ones((10, 10), bool)
    for i in range(10):
        masque[i, i] = masque[i, 9 - i] = False
    if np.array_equal(toile["pixels"][masque], modele["pixels"][masque]):
        scene.niveau_suivant()


def _zone(poste):
    forme, _x, _y, rot = POSTES[poste]
    if forme == "h":
        return {180: [(i, j) for i in range(5) for j in range(10)], 0: [(i, j) for i in range(5, 10) for j in range(10)],
                90: [(i, j) for i in range(10) for j in range(5)], 270: [(i, j) for i in range(10) for j in range(5, 10)]}[rot]
    return {180: [(i, j) for i in range(10) for j in range(i + 1)], 90: [(i, j) for i in range(10) for j in range(9 - i, 10)],
            0: [(i, j) for i in range(10) for j in range(i, 10)], 270: [(i, j) for i in range(10) for j in range(10 - i)]}[rot]


BANDE = {0: (range(0, 3), range(3, 7)), 4: (range(7, 10), range(3, 7)), 6: (range(3, 7), range(0, 3)), 2: (range(3, 7), range(7, 10))}


def step(scene, action):
    nom, r, c = action
    panier, poste, couleur, gobelet = _etat(scene)
    if nom in ("UP", "DOWN", "LEFT", "RIGHT"):
        l, k = ANNEAU[poste]
        l, k = {"UP": (max(0, l - 1), k), "DOWN": (min(2, l + 1), k), "LEFT": (l, max(0, k - 1)),
                "RIGHT": (l, min(2, k + 1))}[nom]
        if (l, k) != (1, 1) and CASE[(l, k)] != poste:
            _recreer(scene, panier, CASE[(l, k)], couleur, gobelet)
    elif nom == "SPACE":
        _peindre(scene, _zone(poste), couleur)
    elif nom == "CLICK":
        touches = scene.a(c, r)
        if not touches:
            return
        s = touches[0]
        if s.get("nom") == "ctwspzkygu":
            p = poste  # le gobelet n'existe qu'au poste pair courant, avec la même rotation
            if p in BANDE:
                lig, col = BANDE[p]
                _peindre(scene, [(i, j) for i in lig for j in col], couleur)
        elif s.get("nom", "").startswith("pqkenviek"):
            ind = _nom(scene, "ydiwkzjkgl")[0]
            scene.placer(ind, s["x"], s["y"] + 5)
            _recreer(scene, panier, poste, int(s["pixels"][2, 2]), gobelet)
