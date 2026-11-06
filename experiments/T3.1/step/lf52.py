"""T3.1 — lf52 : step(scene, action) n'utilisant que les effets fermés de Scene. Pas d'import du jeu.
Le niveau arcengine de lf52 est factice (un sprite 1×1 immobile sur une grille 8×8) : tout le jeu vit dans une scène
interne 64×64 dessinée par l'interface HUD, que le banc exclut. La scène du banc ne change donc JAMAIS et step() n'y applique
aucun effet ; toute la dynamique est tenue ici en état privé (plateau, pions, plateformes, rails, caméra, sélection,
impasse, compteurs, pile d'annulation). Plans des niveaux recopiés de la source (données, pas d'import) ; règles de lf52.md.
Le niveau courant n'est pas lisible dans la scène du banc : à chaque nouvelle Scene (RESET, défaite, changement de niveau),
on devine « niveau suivant » si l'état précédent était à un saut gagnant de la victoire, sinon « même niveau »."""
import copy

GRILLES = {
    1: ['', '.......', '.xx.x..', '.....x.', '    ...', '    .x.', '    ...', '    ...'],
    2: ['....... ', '.xx.x.x->', '....... |', '        |', ' <--,---3', ' |      ', ' |    ..', ' L----x.'],
    3: ['.. ..     ..', '.x .x-,--x..', '.x.x      .xx.', '..x.      ..', '          .xx.', '      <-> ..', '      | | x..',
        '.x.x-,3 L-.x', '...       ..'],
    4: ['', '', '.......', '.xp.p.x-,---x...x.', '.......     .p..p.', '            ......', '            .p..p.',
        '        <---,..p..', '        |', '    .x. | ', '   .p p.p..', '   .----,-.', '   .p p....', '    .x.'],
    5: [' -,-T-P-      ..p..x', '    |        <---T-P>', ' ...|  <--> .|...|. |', ' xp.|.x|  Lx.|.p.|..|',
        ' ...|  |    .|..p|x.|', '    |  |     L---t--3', '  <-t--3       .', '  |            p', '  |           ..x'],
    6: ['', ' ....         ....   ', ' .r..         .x.........>. ', ' .x..         p..p     p |x',
        ' ....         |  |    .?.|.', ' ......       |  |    x| |', ' ......,,-----t--3  ...L-3', ' x.....             x',
        '   x                .'],
    7: ['                 <--->', 'x     r    <-->  |   |', 'p     p    |  ; <tTPTt>', 'L--T--3  <-t-p. | D D |',
        '   |     |    .   | | ;', ' <-t-,> <t->  .p.p. | .', ' |    | |  |  .p.p.   x', ' p    p L->p           ',
        ' .p.p.....3.'],
    8: ['       ', '', ' ........', ' xp...p..', ' ......p.', '<-p...p..', '|...b....', '|...b...x', '|       |',
        'L-,>   <3', '   |   ;', ' ......bb', ' L--P,P-3'],
    9: ['       ', '           x..p.p......', '  ..b..    .........bb.', '  ...b.    .p.....p.p..', '  .....              ..',
        '  ....,--------------..', '  xb..   ', '  .b..x  '],
    10: ['   .x. ', '<-T-T-T->', '| ; ; ; |', '| L-t-3 |', '|       |', '| ...bb |', 'L--b... |', '  ..b.. |', '  b.... |',
         '  ....x 7', '        7', '        7', '        7', '        7'],
}
CASE, PLATEFORME, RAIL, BLOC = "hupkpseyuim", "hupkpseyuim2", "kraubslpehi", "dgxfozncuiz"
VERT, ROUGE, BLEU = "fozwvlovdui", "fozwvlovdui_red", "fozwvlovdui_blue"
LEGENDE = {"x": [VERT, CASE], "r": [ROUGE, CASE], "b": [BLEU, CASE], "o": ["jmbixtieild", CASE], ".": [CASE],
           ",": [PLATEFORME, RAIL], "p": [BLOC, CASE], "P": [BLOC, PLATEFORME, RAIL], "D": [BLOC, PLATEFORME, RAIL + "-up"],
           ";": [PLATEFORME, RAIL + "-up"], "?": [PLATEFORME, RAIL + "-up"], "7": [BLEU, PLATEFORME, RAIL + "-up"],
           "-": [RAIL], "|": [RAIL + "-up"], "L": [RAIL + "-L"], "3": [RAIL + "-3"], "<": [RAIL + "-<"], ">": [RAIL + "->"],
           "T": [RAIL + "-T"], "t": [RAIL + "-t"]}
OFFSET = {1: (10, 5), 2: (6, 8), 10: (5, 3)}
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # haut, droite, bas, gauche (ordre du jeu)
ST = {"niveau": 1, "etat": None}


def _init(n):
    """État interne initial du niveau n : objets {id: [nom, x, y]} (rails et cases fixes compris), caméra, compteurs."""
    objets, k = {}, 0
    for y, ligne in enumerate(GRILLES[n]):
        for x, c in enumerate(ligne):
            for nom in LEGENDE.get(c, []):
                objets[k] = [nom, x, y]
                k += 1
    e = {"n": n, "objets": objets, "offset": OFFSET.get(n, (5, 5)), "coups": 0, "impasse": False, "gris": False,
         "sel": None, "marqueurs": []}
    e["bleus0"] = sum(1 for o in objets.values() if o[0] == BLEU) if n >= 8 else 0
    e["initial"], e["pile"], e["jauge"] = _cliche(e), [], 0
    return e


def _cliche(e):
    return copy.deepcopy({k: e[k] for k in ("objets", "offset", "coups", "impasse", "gris", "sel", "marqueurs")})


def _restaurer(e, c):
    e.update(copy.deepcopy(c))


def _noms(e, x, y):
    return [o[0] for o in e["objets"].values() if o[1] == x and o[2] == y]


def _ids(e, x, y):
    return [k for k, o in e["objets"].items() if o[1] == x and o[2] == y]


def _pions(e):
    return [k for k, o in e["objets"].items() if o[0].startswith(VERT)]


def _restants(e):
    return len(_pions(e)) - e["bleus0"]


def _sautable(e, x, y):
    return any(m in nom for nom in _noms(e, x, y) for m in (VERT, BLOC))


def _libre(e, x, y):
    noms = _noms(e, x, y)
    return (len(noms) == 1 and CASE in noms[0]) or (len(noms) == 2 and PLATEFORME in noms)


def _deselect(e):
    e["sel"], e["marqueurs"] = None, []


def _impasse(e):
    e["gris"] = e["impasse"] = True


def _touche(e, x, y):
    """Objet cliqué parmi pions et marqueurs : le jeu teste la boîte 6×6 de l'image, pas ses pixels opaques."""
    ox, oy = e["offset"]
    if e["sel"] is not None:
        px, py = e["objets"][e["sel"]][1:]
        for d in e["marqueurs"]:
            lx, ly = x - (ox + px * 6 + d[0] * 12), y - (oy + py * 6 + d[1] * 12)
            if 0 <= lx < 6 and 0 <= ly < 6:
                return ("marqueur", d)
    for k in _pions(e):
        _, gx, gy = e["objets"][k]
        if 0 <= x - (ox + gx * 6) < 6 and 0 <= y - (oy + gy * 6) < 6:
            return ("pion", k)
    return None


def _selectionner(e, k):
    _deselect(e)
    _, x, y = e["objets"][k]
    m = [d for d in DIRS if _sautable(e, x + d[0], y + d[1]) and _libre(e, x + 2 * d[0], y + 2 * d[1])]
    if m:
        e["sel"], e["marqueurs"] = k, m  # sinon le pion tremble (visuel seulement)


def _sauter(e, d):
    n, k = e["n"], e["sel"]
    restants = _restants(e)
    nom, x, y = e["objets"][k]
    cx, cy, mx, my = x + 2 * d[0], y + 2 * d[1], x + d[0], y + d[1]
    milieu = next((j for j in _ids(e, mx, my) if VERT in e["objets"][j][0] and "blue" not in e["objets"][j][0]), None)
    if milieu is not None and e["objets"][milieu][0] == nom:
        restants -= 1
        del e["objets"][milieu]
    e["objets"][k][1:] = [cx, cy]
    _deselect(e)
    ox, oy = e["offset"]
    cam = None
    c = (cx, cy)
    if n == 1 and c in [(0, 2), (2, 2), (5, 1)] or n == 2 and c in [(0, 1), (2, 1), (4, 1)]:
        _impasse(e)
    elif n == 3 and (c in [(1, 0), (0, 3), (10, 0), (13, 2), (13, 4)] or c == (10, 2) and restants <= 5
                     or c == (10, 4) and restants <= 4):
        _impasse(e)
    elif n == 4:
        cam = {(7, 3): (-30, 0), (12, 7): (15, -30)}.get(c)
    elif n == 5:
        cam = {(7, 3): (-18, 0), (12, 3): (-33, 0)}.get(c)
    elif n == 6:
        rouge = next((o for o in e["objets"].values() if o[0] == ROUGE), None)
        if c == (16, 2) and nom == VERT:
            if rouge is not None and (rouge[1], rouge[2]) == (6, 6):
                _impasse(e)
        elif c == (7, 6) and (ox, oy) == (5, 5):
            cam = (-20, 0)
        elif nom == VERT and c == (18, 2) and (ox, oy) == (-57, 5):
            cam = (-44, 0)
    elif n == 7:
        if c == (8, 8) and (ox, oy) == (5, 5):
            cam = (-44, 0)
        elif cx == 16 and (ox, oy) == (-39, 5):
            cam = (-40, 0)
    elif n == 9 and c == (6, 5):
        cam = (-20, 0)
    if cam:
        e["offset"] = (ox + cam[0], oy + cam[1])
    return restants == 1 or (n in (6, 7) and restants == 2)


def _fleche(e, dx, dy):
    n = e["n"]
    e["coups"] += 1
    plats = [k for k, o in e["objets"].items() if o[0] == PLATEFORME]
    cle = (lambda k: e["objets"][k][1]) if dx else (lambda k: e["objets"][k][2])
    plats = sorted(plats, key=cle, reverse=(dx > 0) if dx else (dy > 0))
    deja = False
    for p in plats:
        _, px, py = e["objets"][p]
        noms = _noms(e, px + dx, py + dy)
        vec = (0, 0)
        if PLATEFORME not in noms and any(RAIL in s for s in noms):
            _deselect(e)
            for j in _ids(e, px, py):
                o = e["objets"][j]
                if RAIL in o[0]:
                    continue
                if o[0] == VERT:
                    if n <= 2 or n in (7, 10) or (n == 4 and o[2] >= 11):
                        vec = (0, 0)
                    elif n == 3:
                        vec = (-dx * 8, 0)
                    elif n in (5, 6):
                        vec = (-dx * 6, 0)
                    elif n == 8:
                        vec = (0, -dy * 6)
                    else:
                        vec = (-dx * 6, -dy * 6)
                o[1], o[2] = o[1] + dx, o[2] + dy
        if vec != (0, 0) and not deja:
            deja = True
            if n != 5 and e["offset"][0] >= 5 and vec[0] > 0:
                return
            e["offset"] = (e["offset"][0] + vec[0], e["offset"][1] + vec[1])


def _clic(e, x, y):
    """Renvoie True si le clic gagne le niveau."""
    if e["impasse"] and x < 16 and y > 48:  # bouton reset : état initial, pile vidée, compteur interne remis à 0
        _restaurer(e, e["initial"])
        e["pile"] = []
        return False
    e["pile"].append(_cliche(e))
    e["coups"] += 1
    t = _touche(e, x, y)
    if t and t[0] == "pion":
        _selectionner(e, t[1])
    elif t and t[0] == "marqueur":
        return _sauter(e, t[1])
    elif e["impasse"] and 2 <= x < 13 and 51 <= y < 64:  # clic sur le bouton reset déjà levé : drapeau déjà vrai
        pass
    elif e["n"] == 1 and (e["impasse"] or len([k for k in _pions(e) if e["objets"][k][0] == VERT]) == 5):
        pass  # N1 : indice clignotant, la sélection reste
    else:
        _deselect(e)
    return False


def _proche_victoire(e):
    if e is None or e["sel"] is None:
        return False
    cible = 2 if e["n"] in (6, 7) else 1
    return _restants(e) == cible + 1


def etat():
    return ST["etat"]


def step(scene, action):
    e = getattr(scene, "_lf52", None)
    if e is None:  # nouvelle Scene du banc : début, RESET, défaite ou niveau suivant (indiscernables dans la scène)
        prec = ST["etat"]
        if prec is not None and _proche_victoire(prec):
            ST["niveau"] = min(prec["n"] + 1, 10)
        elif prec is not None:
            ST["niveau"] = prec["n"]
        e = _init(ST["niveau"])
        scene._lf52 = ST["etat"] = e
    nom, r, c = action
    e["jauge"] += 1
    gagne = False
    if nom in ("UP", "DOWN", "LEFT", "RIGHT"):
        e["pile"].append(_cliche(e))
        _fleche(e, *{"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}[nom])
    elif nom == "CLICK":
        gagne = _clic(e, c, r)
    elif nom == "UNDO":
        if e["pile"]:
            _restaurer(e, e["pile"].pop())
    elif nom == "SPACE":  # ACTION5 (non offerte) : déclenche l'impasse
        e["pile"].append(_cliche(e))
        e["coups"] += 1
        _impasse(e)
    # la scène du banc (sprite 1×1 factice) ne change pas : aucun effet visible à appliquer
    if gagne:
        scene.gagner() if e["n"] == 10 else scene.niveau_suivant()
    elif e["coups"] >= (64 if e["n"] == 1 else 320 if e["n"] < 6 else 640):
        scene.perdre()
