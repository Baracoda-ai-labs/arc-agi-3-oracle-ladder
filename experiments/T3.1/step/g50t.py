"""T3.1 — g50t : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
État privé (module) : trajet du joueur, fantômes et leurs trajets, compteur de boucles, coups (jauge), occupants des dalles,
valeur des fils, état des portes. Couvert : déplacement sur masque, portes 8/11 câblées par fil, écrasement, boucle
temporelle (rembobinage + fantôme), HUD (curseur, marques, jauge), sortie. Non couvert : téléporteur, ennemi sur rail.
Convention du moteur reprise : un pixel « présent » est tout pixel ≠ -1 (les -2 comptent)."""

JOUEUR, SOL, SORTIE, PORTE, DALLE, FIL = "qftsebtxuc", "rsrdfsruqh", "gilbljmfbc", "kjrcloicja", "medyellngi", "hxztohfdlx"
EMPL, CURSEUR, JAUGE = "gpkhwmwioo", "ovhuyqtghw", "ppfvilwwnk"
MARQ_COUR, MARQ_USE = "oewlmipzzz", "opsxquspoc"
PAS = 6
DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
ST = {}
DEPARTS = {}  # signature du niveau -> position de départ du joueur (vue au premier coup du niveau)


def _px(s, x, y):
    p = s["pixels"]
    dx, dy = x - s["x"], y - s["y"]
    if 0 <= dy < p.shape[0] and 0 <= dx < p.shape[1]:
        return int(p[dy, dx])
    return -1


def _centre(s):
    return s["x"] + s["pixels"].shape[1] // 2, s["y"] + s["pixels"].shape[0] // 2


def _boites(a, b):
    ha, wa = a["pixels"].shape
    hb, wb = b["pixels"].shape
    return a["x"] < b["x"] + wb and a["x"] + wa > b["x"] and a["y"] < b["y"] + hb and a["y"] + ha > b["y"]


def _sous(fil, s, dx=0, dy=0):
    cx, cy = _centre(s)
    return _px(fil, cx + dx, cy + dy) != -1


def _dir_porte(p):
    """Côté ouvert (milieu de bord non 5) = sens de glissement."""
    px = p["pixels"]
    h, w = px.shape
    for (x, y), d in (((w // 2, h - 1), (0, 1)), ((0, h // 2), (-1, 0)), ((w // 2, 0), (0, -1)), ((w - 1, h // 2), (1, 0))):
        if px[y, x] != 5:
            return d
    return (0, 1)


def _vis(scene, tag):
    return [s for s in scene.par_tag(tag) if s["visible"]]


def _signature(scene):
    sol = scene.par_tag(SOL)[0]
    return (sol["x"], sol["y"], sol["pixels"].shape, tuple(sorted((s["x"], s["y"]) for s in scene.par_tag(SORTIE))))


def _init(scene):
    sig = _signature(scene)
    mob = _vis(scene, JOUEUR)
    joueur = [s for s in mob if 9 in s["pixels"]][-1]
    fantomes = [[s, []] for s in mob if s is not joueur]
    DEPARTS.setdefault(sig, (joueur["x"], joueur["y"]))
    portes = []
    for p in scene.par_tag(PORTE):
        cx, cy = _centre(p)
        portes.append({"s": p, "dir": _dir_porte(p), "bascule": int(p["pixels"][cy - p["y"], cx - p["x"]]) == 11,
                       "ouverte": False, "cible": None})
    fils = []
    for f in scene.par_tag(FIL):
        sorties = []
        for i, d in enumerate(portes):
            p = d["s"]
            if _boites(f, p) and _sous(f, p):
                sorties.append(i)
            elif _sous(f, p, -d["dir"][0] * PAS, -d["dir"][1] * PAS):  # porte vue ouverte (resynchronisation)
                d["ouverte"] = True
                sorties.append(i)
        fils.append({"s": f, "val": False, "sorties": sorties})
    dalles = []
    for dl in scene.par_tag(DALLE):
        fil = next((k for k, f in enumerate(fils) if _boites(dl, f["s"]) and _sous(f["s"], dl)), None)
        dalles.append({"s": dl, "occ": set(), "val": False, "fil": fil})
    empl = sorted(scene.par_tag(EMPL), key=lambda s: s["x"])
    marques = []
    for e in empl:
        mc = next(s for s in scene.sprites if s.get("nom") == MARQ_COUR and (s["x"], s["y"]) == (e["x"], e["y"]))
        mu = next(s for s in scene.sprites if s.get("nom") == MARQ_USE and (s["x"], s["y"]) == (e["x"], e["y"]))
        marques.append((mc, mu))
    compteur = next((i for i, (mc, _) in enumerate(marques) if mc["visible"]), 0)
    jauge = scene.par_tag(JAUGE)[0]
    ST.clear()
    ST.update(scene=id(scene), sig=sig, joueur=joueur, fantomes=fantomes, trajet=[], depart=DEPARTS[sig], portes=portes,
              fils=fils, dalles=dalles, empl=empl, marques=marques, compteur=compteur, coups=-2 * jauge["x"],
              jauge=jauge, rembobine=False, mort=False)
    for d in dalles:  # occupants actuels, sans émission
        for m in [joueur] + [g for g, _ in fantomes]:
            if _zone(m) is d:
                d["occ"].add(id(m))
        d["val"] = bool(d["occ"])
        if d["fil"] is not None and d["val"]:
            ST["fils"][d["fil"]]["val"] = True


def _zone(m):
    cx, cy = _centre(m)
    for d in ST["dalles"]:
        if _px(d["s"], cx, cy) != -1:
            return d
    return None


def _signal_dalle(m, valeur):
    d = _zone(m)
    if d is None:
        return
    if valeur:
        d["occ"].add(id(m))
    else:
        d["occ"].discard(id(m))
    v = bool(d["occ"])
    if v == d["val"]:
        return
    d["val"] = v
    if d["fil"] is None:
        return
    f = ST["fils"][d["fil"]]
    if f["val"] == v:
        return
    f["val"] = v
    for i in f["sorties"]:
        _signal_porte(ST["portes"][i], v)


def _signal_porte(d, v):
    if d["bascule"]:
        if not v:
            return
        if d["ouverte"]:
            v = False
    if d["ouverte"] == v:
        return
    d["ouverte"] = v
    p = d["s"]
    k = 1 if v else -1
    d["cible"] = (p["x"] + d["dir"][0] * PAS * k, p["y"] + d["dir"][1] * PAS * k, ST["rembobine"])


def _legal(scene, m, x, y):
    cx, cy = x + m["pixels"].shape[1] // 2, y + m["pixels"].shape[0] // 2
    if _px(scene.par_tag(SOL)[0], cx, cy) == -1:
        return False
    return not any(d["s"]["visible"] and _px(d["s"], cx, cy) != -1 for d in ST["portes"])


def _bouger(scene, m, dx, dy, moves):
    x, y = m["x"] + dx * PAS, m["y"] + dy * PAS
    if not _legal(scene, m, x, y):
        return False
    _signal_dalle(m, False)
    moves.append((m, x, y))
    return True


def _appliquer(scene, moves):
    """Fin des animations d'un tic : mobiles et portes à leur cible, écrasement par une porte qui finit fermée."""
    for m, x, y in moves:
        scene.placer(m, x, y)
    for d in ST["portes"]:
        if d["cible"] is None:
            continue
        x, y, remb = d["cible"]
        d["cible"] = None
        scene.placer(d["s"], x, y)
        j = ST["joueur"]
        if not remb and not d["ouverte"] and j["visible"] and _boites(j, d["s"]) and _px(d["s"], *_centre(j)) != -1:
            scene.montrer(j, False)
            ST["mort"] = True


def _presser():
    _signal_dalle(ST["joueur"], True)
    for g, _ in ST["fantomes"]:
        _signal_dalle(g, True)


def _deplacement(scene, dx, dy):
    moves = []
    if not _bouger(scene, ST["joueur"], dx, dy, moves):
        return
    ST["trajet"].append((dx, dy))
    i = len(ST["trajet"]) - 1
    for g, t in ST["fantomes"]:
        if i < len(t):
            _bouger(scene, g, t[i][0], t[i][1], moves)
    _appliquer(scene, moves)
    _presser()
    _appliquer(scene, [])


def _recul(scene):
    dx, dy = ST["trajet"].pop()
    i = len(ST["trajet"])
    moves = []
    for g, t in ST["fantomes"]:
        if i < len(t):
            _bouger(scene, g, -t[i][0], -t[i][1], moves)
    _bouger(scene, ST["joueur"], -dx, -dy, moves)
    _appliquer(scene, moves)


def _boucle(scene):
    if not ST["trajet"]:
        return
    copie = list(ST["trajet"])
    ST["rembobine"] = False
    _recul(scene)
    ST["rembobine"] = bool(ST["trajet"])
    while True:
        _presser()
        _appliquer(scene, [])
        if ST["rembobine"]:
            _recul(scene)
            if not ST["trajet"]:
                ST["rembobine"] = False
            continue
        break
    ST["compteur"] += 1
    j = ST["joueur"]
    scene.placer(j, *ST["depart"])
    if ST["compteur"] == len(ST["empl"]):
        for g, _ in ST["fantomes"]:
            scene.montrer(g, False)
        ST["fantomes"] = []
        ST["compteur"] = 0
    else:
        neuf = scene.creer(j, *ST["depart"])
        scene.recolorer(j, 9, 2)
        ST["fantomes"].append([j, copie])
        ST["joueur"] = neuf
    c = ST["compteur"]
    e = ST["empl"][c]
    scene.placer(scene.par_tag(CURSEUR)[0], e["x"], e["y"])
    if c == 0:
        for mc, mu in ST["marques"]:
            scene.montrer(mc, False)
            scene.montrer(mu, False)
    else:
        scene.montrer(ST["marques"][c - 1][0], False)
        scene.montrer(ST["marques"][c - 1][1], True)
    scene.montrer(ST["marques"][c][0], True)
    scene.montrer(ST["marques"][c][1], False)


def step(scene, action):
    if ST.get("scene") != id(scene) or ST.get("sig") != _signature(scene):
        _init(scene)
    a = action[0]
    if a in DIRS:
        _deplacement(scene, *DIRS[a])
    elif a == "SPACE":
        _boucle(scene)
    else:
        return
    ST["coups"] += 1
    if ST["coups"] % 2 == 0:
        scene.deplacer(ST["jauge"], -1, 0)
    if -ST["jauge"]["x"] > ST["jauge"]["pixels"].shape[1] or ST["mort"]:
        scene.perdre()
        return
    s = scene.par_tag(SORTIE)[0]
    j = ST["joueur"]
    if (s["x"] + 1, s["y"] + 1) == (j["x"], j["y"]):
        scene.niveau_suivant()
