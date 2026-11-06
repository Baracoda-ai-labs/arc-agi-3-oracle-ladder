"""T3.1 — bp35 : step(scene, action). Pas d'import du jeu, aucune lecture du moteur.
Le jeu a son propre moteur de grille (les niveaux arcengine sont des leurres 8×8 à un pixel) et dessine tout dans son HUD,
que le banc exclut : la scène visible ne change JAMAIS, donc step() n'y touche pas (aucun effet visible).
Toute la dynamique est tenue en ÉTAT PRIVÉ (attribut `scene._bp35`) : grille 11×H (gy = 0 = dernière ligne du gabarit),
joueur, regard, gravité, compteur de coups (parité de la marée), caméra camY, jauge, pile d'annulation.
Données : gabarits des 9 niveaux recopiés comme constantes (description bp35.md + source, lecture seule) ; règles R1-R13.
Limite : la scène leurre est identique à tous les niveaux et le banc n'appelle pas step() sur le coup qui gagne/perd ni sur
RESET ; à une scène neuve on infère le niveau (suivant si le dernier état permettait de gagner en un coup, sinon le même)."""
import copy

LIBRES = {"2", "m"}  # traversables (fantôme, tête de marée) ; case vide aussi
BLOQUE_G = {"o", "g", "1", "x", "y"}  # R10 : voisine qui retient le joueur après l'inversion
_DERNIER = {"etat": None}


def _neuf(niveau):
    rows = GABARITS[niveau][::-1]
    grille, joueur = {}, None
    for gy, r in enumerate(rows):
        for gx, c in enumerate(r):
            if c == "n":
                joueur = (gx, gy)
            elif c != " ":
                grille[(gx, gy)] = [c]
    return {"niveau": niveau, "grille": grille, "joueur": joueur, "regard": 1, "grav": -1, "compteur": 0,
            "camY": joueur[1] * 6 - 36, "jauge": 0, "pile": [], "issue": None}


def _cases(e, c, avec_joueur=False):
    lst = list(e["grille"].get(c, []))
    if avec_joueur and c == e["joueur"]:
        lst.append("P")
    return lst


def _libre(lst):
    return set(lst) <= LIBRES


def _decalage(e):
    return -5 if e["grav"] == -1 else 5


def _chute(e, depart):
    """Chute depuis `depart` (exclu) dans le sens de la gravité → (k, case finale, gemme, pointe)."""
    dy = e["grav"]
    prec, cur, k = depart, (depart[0], depart[1] + dy), 0
    while _libre(_cases(e, cur)):
        prec, cur, k = cur, (cur[0], cur[1] + dy), k + 1
    lst = _cases(e, cur)
    if lst == ["+"]:
        return k + 1, cur, True, False
    if lst in (["v"], ["u"]):
        return k + 1, prec, False, True
    return k, prec, False, False


def _maree(e):
    """R11 : après un pas horizontal sans chute (ou bloqué). Vrai = défaite."""
    if e["niveau"] > 3 or e["compteur"] % 2:
        return False
    tete = [c[1] for c, l in e["grille"].items() if "m" in l]
    perdu = bool(tete) and e["joueur"][1] == tete[0]
    g2 = {}
    for (x, y), l in e["grille"].items():
        for o in l:
            g2.setdefault((x, y - 1) if o in "mw" else (x, y), []).append(o)
    e["grille"] = g2
    return perdu


def _fin(e, gemme, pointe):
    if gemme:
        e["issue"] = "victoire"
    elif pointe:
        e["issue"] = "defaite"


def _pas(e, dx):
    e["regard"] = dx
    e["compteur"] += 1
    px, py = e["joueur"]
    cible = (px + dx, py)
    lst = ["o"] if cible[0] < 0 else _cases(e, cible)
    if lst == ["+"]:
        e["joueur"], e["issue"] = cible, "victoire"
    elif _libre(lst):
        k, pos, gemme, pointe = _chute(e, cible)
        if k == 0:
            perdu = _maree(e)
            e["joueur"] = cible
            if perdu:
                e["issue"] = "defaite"
        else:
            e["joueur"], e["camY"] = pos, pos[1] * 6 - 31 + _decalage(e)
            _fin(e, gemme, pointe)
    elif _maree(e):
        e["issue"] = "defaite"


def _sous_clic(e, case, force):
    """R9/R10 : évalué AVANT que l'objet cliqué ne disparaisse."""
    px, py = e["joueur"]
    voisine = (px, py + e["grav"])
    if not force and case != voisine:
        return
    lst = _cases(e, voisine)
    if "o" in lst or (force and set(lst) & BLOQUE_G):
        e["camY"] = py * 6 - 31 + _decalage(e)
        return
    _, pos, gemme, pointe = _chute(e, voisine)
    e["joueur"], e["camY"] = pos, pos[1] * 6 - 31 + _decalage(e)
    _fin(e, gemme, pointe)


def _oter(e, case, o):
    e["grille"][case].remove(o)
    if not e["grille"][case]:
        del e["grille"][case]


def _clic(e, row, col):
    e["compteur"] += 1
    case = (col // 6, (row + e["camY"]) // 6)
    lst = _cases(e, case, avec_joueur=True)
    if len(lst) != 1:
        return
    o = lst[0]
    if o == "x":
        _sous_clic(e, case, False)
        _oter(e, case, "x")
    elif o == "y":
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            v = (case[0] + dx, case[1] + dy)
            if not _cases(e, v, avec_joueur=True):
                e["grille"][v] = ["y"]
        _sous_clic(e, case, False)
        _oter(e, case, "y")
    elif o in ("1", "2"):
        _sous_clic(e, case, False)
        e["grille"][case].append("2" if o == "1" else "1")
        _oter(e, case, o)
    elif o == "g":
        e["grav"] = -e["grav"]
        _sous_clic(e, case, True)
        _oter(e, case, "g")


INSTANTANE = ("grille", "joueur", "regard", "grav", "compteur", "camY")


def appliquer(e, action):
    """Transition privée complète (R1-R13 + jauge). Modifie e sur place."""
    nom, row, col = action
    if nom in ("LEFT", "RIGHT", "CLICK"):
        e["pile"].append(copy.deepcopy({k: e[k] for k in INSTANTANE}))
        if nom == "CLICK":
            _clic(e, row, col)
        else:
            _pas(e, -1 if nom == "LEFT" else 1)
        e["jauge"] += 1
    elif nom == "UNDO":
        if e["pile"]:
            e.update(e["pile"].pop())
        e["jauge"] += 1
    if e["issue"] is None and e["jauge"] >= (64 if e["niveau"] <= 6 else 128):
        e["issue"] = "defaite"


def _gagnable(e):
    """Un coup suffit-il à gagner ? (sert à deviner le niveau d'une scène neuve)."""
    if e is None or e["issue"] is not None:
        return e is not None and e["issue"] == "victoire"
    coups = [("LEFT", None, None), ("RIGHT", None, None)]
    for (gx, gy), l in e["grille"].items():
        if len(l) == 1 and l[0] in "xy12g" and 0 <= gy * 6 - e["camY"] < 64:
            coups.append(("CLICK", gy * 6 - e["camY"], gx * 6))
    for a in coups:
        f = copy.deepcopy(e)
        f["pile"] = []
        appliquer(f, a)
        if f["issue"] == "victoire":
            return True
    return False


def step(scene, action):
    e = getattr(scene, "_bp35", None)
    if e is None:  # scène neuve : départ, RESET, défaite ou niveau gagné (le banc ne nous montre pas ce coup)
        d = _DERNIER["etat"]
        niveau = 1 if d is None else min(9, d["niveau"] + 1) if _gagnable(d) else d["niveau"]
        e = scene._bp35 = _neuf(niveau)
    appliquer(e, action)
    _DERNIER["etat"] = e
    if e["issue"] == "victoire":
        scene.gagner() if e["niveau"] == 9 else scene.niveau_suivant()
    elif e["issue"] == "defaite":
        scene.perdre()
    # aucun effet visible : le monde de bp35 n'existe que dans son HUD, exclu de la comparaison


# Gabarits des niveaux 1-9 (lignes du haut vers le bas, comme dans la source ; gy = 0 = dernière ligne).
GABARITS = {
    1: [
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'mmmmmmmmmmm',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo n     oo',
        'ooooooo ooo',
        'oo       oo',
        'oo       oo',
        'oooooxxxxoo',
        'ooooo    oo',
        'ooxxx    oo',
        'ooxxx    oo',
        'ooxxxoooooo',
        'oo       oo',
        'oo       oo',
        'oo  xxx  oo',
        'oo       oo',
        'oo       oo',
        'oooooxxxooo',
        'oo       oo',
        'oo +     oo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    2: [
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'mmmmmmmmmmm',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo n     oo',
        'ooxxxxxxxoo',
        'ooxxxxxxxoo',
        'oo   o   oo',
        'oo   o   oo',
        'oovvvo   oo',
        'oooooo   oo',
        'ooxxxx   oo',
        'ooxxxx   oo',
        'ooxoooxxxoo',
        'oo       oo',
        'oo       oo',
        'oo    vvvoo',
        'oooooxooooo',
        'oooooxooooo',
        'oo       oo',
        'oo      voo',
        'ooxxxoooooo',
        'oo       oo',
        'oov vvvvvoo',
        'oooxooooooo',
        'oooxxxxxxoo',
        'oooxooooxoo',
        'oooxooooxoo',
        'oo       oo',
        'oovvv    oo',
        'ooooo    oo',
        'oo     xxoo',
        'ooxxxxxxxoo',
        'oo       oo',
        'oo   +vvvoo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    3: [
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'wwwwwwwwwww',
        'mmmmmmmmmmm',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo   1   oo',
        'oo n 1   oo',
        'ooooooxxxoo',
        'oo       oo',
        'oo       oo',
        'oo       oo',
        'oo 222ooooo',
        'oo       oo',
        'oo vvvv  oo',
        'oo oooo  oo',
        'oo       oo',
        'ooo  11  oo',
        'ooooo22  oo',
        'ooooovv  oo',
        'ooooooo  oo',
        'oo       oo',
        'oo       oo',
        'oo11222oooo',
        'oo     oooo',
        'oo  vvvoooo',
        'oo  ooooooo',
        'oo   1   oo',
        'oo   1 + oo',
        'oo1111111oo',
        'oo       oo',
        'oovvvvvvvoo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    4: [
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'oooogoooooo',
        'ooooooooooo',
        'oo       oo',
        'oo       oo',
        'oo  +    oo',
        'oo       oo',
        'oovv vv  oo',
        'oooooooxxoo',
        'ooogogoxxoo',
        'ooooooo  oo',
        'oo    o  oo',
        'oo       oo',
        'oo   xxxxoo',
        'oo       oo',
        'ooxxooooooo',
        'oo       oo',
        'oo       oo',
        'oovvn    oo',
        'oooooo   oo',
        'ooooooo  oo',
        'oooooooo oo',
        'oo       oo',
        'oo       oo',
        'ooooooooooo',
        'ooooogooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    5: [
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'oooooooogoo',
        'ooouuoooooo',
        'ooo  oooooo',
        'oooxxoooooo',
        'ooo  oooooo',
        'ooo     ooo',
        'oo        o',
        'oo        o',
        'oo 22oooxxo',
        'oo vvoxx  o',
        'oo ooo    o',
        'oo ooo  vvo',
        'oo      ooo',
        'ooooooxxooo',
        'oooooo  ooo',
        'oouuuu  ooo',
        'oo      ooo',
        'oo n    g o',
        'ooooooooo o',
        'ooooooooo o',
        'oooo   xxxo',
        'oooo   xxxo',
        'oooo + vvvo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    6: [
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'o + g    oo',
        'o   o    oo',
        'oooooooo oo',
        'oooooooo oo',
        'oooooooo oo',
        'oouuuuuu oo',
        'oo    22 oo',
        'oo       oo',
        'oo n     oo',
        'oooooogoooo',
        'oo       oo',
        'oo222ooo oo',
        'oo     o oo',
        'oovvv    oo',
        'oooooo oooo',
        'oooooo oooo',
        'oouuuu   oo',
        'oo       oo',
        'oo2222122oo',
        'oo       oo',
        'oo       oo',
        'oooo vvvvoo',
        'oooo oooooo',
        'oooo     oo',
        'ooooooo  oo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'oooooooogoo',
        'ooooooooooo',
    ],
    7: [
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'go   oooooo',
        'go   oo   o',
        'go + oo o o',
        'go      u o',
        'go        o',
        'gooooooo  o',
        'go    2o  o',
        'go        o',
        'go n  2o  o',
        'gooooooo  o',
        'go u222u  o',
        'go  222   o',
        'go  222   o',
        'go o222 o o',
        'go o222 o o',
        'go oooooo o',
        'go 2 u uo o',
        'go 2 1 2o o',
        'go 22 12o o',
        'go 2v v2o o',
        'goooooo2  o',
        'goooooo2  o',
        'goooooo2o o',
        'ooooooo2ovo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    8: [
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'o         o',
        'o         o',
        'o  n      o',
        'ooooo   ooo',
        'o         o',
        'o y       o',
        'o         o',
        'ovvvvvvv  o',
        'oooooooo  o',
        'o      1  o',
        'o      oooo',
        'o         o',
        'o111111111o',
        'o         o',
        'o      oooo',
        'o      o +o',
        'o  y   o1oo',
        'o         o',
        'o         o',
        'o         o',
        'o         o',
        'o         o',
        'o         o',
        'o         o',
        'ov       vo',
        'oov     voo',
        'ooov   vooo',
        'oooo   oooo',
        'oooovvvoooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooogooooo',
        'ooooooooooo',
        'ooooooooooo',
    ],
    9: [
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        '  + ooooooo',
        '    ooooooo',
        ' oooooooooo',
        ' o        o',
        ' o        o',
        'go n      o',
        ' oooo   ooo',
        'go        o',
        ' o        o',
        ' o    y   o',
        ' o        o',
        ' o        o',
        ' o        o',
        ' o   vvvvvo',
        ' oxxxoooooo',
        'go   ouuuuo',
        ' o   o    o',
        ' o   o    o',
        ' o   o  o o',
        'go      o o',
        ' o      o o',
        'govvvvvvo o',
        ' oooooooo o',
        ' ouuuuuuu o',
        ' o        o',
        'go11111111o',
        ' o        o',
        ' o  x     o',
        ' o        o',
        ' o        o',
        ' o        o',
        ' o        o',
        ' x     y  o',
        ' o        o',
        'oovvvvvvvvo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ooooooooooo',
        'ogggggggggo',
        'ooooooooooo',
    ],
}
