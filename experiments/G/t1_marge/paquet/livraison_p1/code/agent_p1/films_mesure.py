# SPDX-License-Identifier: MIT-0
"""CW-441/442 [session E] : EXTRACTEUR AUTOMATIQUE D'ÉVÉNEMENTS DE FILM (sans LLM). Un film = les images qu'un coup rend
(`f.frame`, CHRYS_FILMS de D) ; `avant` = image finale du coup précédent. Pour chaque coup, `evenements(avant, images)` rend :
  (1) trajectoires : objets (composante 4-connexe d'une couleur, taille gardée) suivis image par image ; positions par
      lesquelles ils PASSENT, pas seulement où ils finissent ; `revient` si l'objet finit là où il était ;
  (2) transitoires : cases et couleurs touchées seulement pendant l'animation (différentes de l'avant ET de l'après) ;
      `ephemeres` = couleurs absentes avant et après ;
  (3) contacts : deux objets qui se touchent (4-voisinage ou recouvrement) au milieu du film sans se toucher ni avant ni
      après ; et `recolores` : cases d'un objet qui changent de couleur au contact puis reviennent ;
  (4) signaux : `flash` (grande zone, ≥ 20 cases, qui change de couleur puis revient à l'identique, le reste de l'image
      pouvant changer ; ≥ 4 cases si le coup ne laisse aucune trace : clignotement d'un refus) ; `retour_clic` si la zone entoure le point
      cliqué (anneau d'appui, su15) ; `curseur` (petite
      zone transitoire dont la position avance pas à pas sur ≥ 3 images, comme un balayage de vérification).
Aucune vérité de jeu : seulement les pixels du film. Contrôle positif : experiments/E_franzen/controle_films.py ; branchement : moteur.MoteurC.proposer sous CHRYS_FILMS_EVT."""
import numpy as np

GRAND_FLASH = 20
TAILLE_MIN = 4  # en dessous, motifs de décor (damiers d'un pixel) : pas des objets suivis
PETIT = 12


def composantes(masque):
    """Composantes 4-connexes d'un masque booléen → liste d'ensembles de (x, y)."""
    vu = np.zeros_like(masque, bool)
    out = []
    for y, x in zip(*np.nonzero(masque), strict=True):
        if vu[y, x]:
            continue
        pile, comp = [(y, x)], set()
        vu[y, x] = True
        while pile:
            a, b = pile.pop()
            comp.add((b, a))
            for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= c < masque.shape[0] and 0 <= d < masque.shape[1] and masque[c, d] and not vu[c, d]:
                    vu[c, d] = True
                    pile.append((c, d))
        out.append(comp)
    return out


def _objets(g, couleurs):
    return [(int(c), comp) for c in couleurs for comp in composantes(g == c)]


def _coin(comp):
    return min(x for x, _ in comp), min(y for _, y in comp)


def _voisins(a, b):
    return bool(a & b) or any((x + dx, y + dy) in b for x, y in a for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def trajectoires(avant, images):
    """Objets des couleurs qui bougent : chemin des coins (x, y) image par image, même couleur et même taille."""
    seq = [avant, *images]
    change = np.zeros_like(avant, bool)
    for g in images:
        change |= g != avant
    if not change.any():
        return []
    couleurs = set(np.unique(avant[change]).tolist()) | {c for g in images for c in np.unique(g[change]).tolist()}
    out = []
    for c, comp in _objets(avant, couleurs):
        if len(comp) > 400 or len(comp) < TAILLE_MIN or not any(change[y, x] for x, y in comp):
            continue
        chemin, cur, cases = [_coin(comp)], comp, [comp]
        for g in seq[1:]:
            cands = [k for k in composantes(g == c) if abs(len(k) - len(cur)) <= max(1, len(cur) // 5)]
            if not cands:
                chemin.append(None)
                cases.append(set())
                continue
            cx, cy = chemin[-1] if chemin[-1] is not None else _coin(cur)
            cur = min(cands, key=lambda k: abs(_coin(k)[0] - cx) + abs(_coin(k)[1] - cy))
            chemin.append(_coin(cur))
            cases.append(cur)
        vus = [p for p in chemin if p is not None]
        distincts = list(dict.fromkeys(vus))
        if len(distincts) < 2:
            continue
        out.append({"couleur": c, "taille": len(comp), "chemin": distincts, "n_images": len(chemin),
                    "intermediaires": len([p for p in distincts if p not in (vus[0], vus[-1])]),
                    "revient": vus[0] == vus[-1], "_cases": cases})
    return out


def transitoires(avant, images):
    apres = images[-1]
    tr = np.zeros_like(avant, bool)
    cols = set()
    for g in images[:-1]:
        m = (g != avant) & (g != apres)
        tr |= m
        cols |= set(np.unique(g[m]).tolist())
    eph = sorted(cols - set(np.unique(avant).tolist()) - set(np.unique(apres).tolist()))
    return {"cases": int(tr.sum()), "couleurs": sorted(cols), "ephemeres": eph}, tr


def _sillage(trajs, k, avant):
    """Cases expliquées par le passage d'un objet suivi à l'image k du film (k = 0 : 1re image après l'avant), ou avant."""
    m = np.zeros_like(avant, bool)
    for t in trajs:
        for idx in (0, k + 1):
            for x, y in t["_cases"][idx] if idx < len(t["_cases"]) else ():
                m[y, x] = True
    return m


def _derniere(cases, k):
    """Cases de l'objet à l'image k, ou à sa dernière image connue s'il a quitté sa couleur (recoloré au contact)."""
    for j in range(min(k, len(cases) - 1), -1, -1):
        if cases[j]:
            return cases[j]
    return set()


def _proches(a, b):
    """Recouvrement, ou distance d'au plus une case (au contact, l'objet recoloré n'est plus suivi)."""
    return any((x + dx, y + dy) in b for x, y in a for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2))


def contacts(avant, images, trajs):
    """Deux objets SUIVIS (qui bougent tous deux) qui se touchent au milieu du film seulement ; cases recolorées pendant
    le film puis rétablies, HORS du sillage des objets suivis (sinon un simple glissement serait une recoloration)."""
    apres, out = images[-1], []
    for k in range(len(images) - 1):
        for i, ta in enumerate(trajs):
            for tb in trajs[i + 1:]:
                a, b = _derniere(ta["_cases"], k + 1), _derniere(tb["_cases"], k + 1)  # recoloré au contact (m0r0) :
                if a and b and _proches(a, b) and not _voisins(ta["_cases"][0], tb["_cases"][0]) and \
                        not any(x["a"] == ta["couleur"] and x["b"] == tb["couleur"] for x in out):
                    out.append({"a": ta["couleur"], "b": tb["couleur"], "image": k})
    rec = []
    for k, g in enumerate(images[:-1]):
        m = (g != avant) & (avant == apres) & ~_sillage(trajs, k, avant)
        for comp in composantes(m):
            ys = [y for _, y in comp]
            xs = [x for x, _ in comp]
            c_av = {int(avant[y, x]) for x, y in comp}
            c_mi = {int(g[y, x]) for x, y in comp}
            if c_mi - c_av and len(comp) >= 2:
                rec.append({"de": sorted(c_av), "vers": sorted(c_mi - c_av), "cases": len(comp),
                            "boite": (min(xs), min(ys), max(xs), max(ys))})
    return out, _uniques(rec)


def _touche(g, ca, cb):
    a = {(x, y) for y, x in zip(*np.nonzero(g == ca), strict=True)}
    b = {(x, y) for y, x in zip(*np.nonzero(g == cb), strict=True)}
    return bool(a) and bool(b) and _voisins(a, b)


def _uniques(L):
    vus, out = set(), []
    for x in L:
        k = (tuple(x["de"]), tuple(x["vers"]))
        if k not in vus:
            vus.add(k)
            out.append(x)
    return out


def signaux(avant, images, tr_masque, trajs=(), clic=None):
    apres, out = images[-1], []
    if True:  # la ZONE qui flashe revient à l'identique ; le reste de l'image peut changer (jauge, compteur)
        for k, g in enumerate(images[:-1]):
            m = (g != avant) & (apres == avant) & ~_sillage(trajs, k, avant)
            seuil = 4 if np.array_equal(avant, apres) else GRAND_FLASH  # coup sans effet durable : un petit clignotement
            for comp in composantes(m):                                  # (panneau refusé) suffit
                if len(comp) >= seuil:
                    xs, ys = [x for x, _ in comp], [y for _, y in comp]
                    autour = clic is not None and min(xs) - 2 <= clic[0] <= max(xs) + 2 and min(ys) - 2 <= clic[1] <= max(ys) + 2
                    out.append({"sorte": "retour_clic" if autour else "flash", "image": k, "cases": len(comp),
                                "couleurs": sorted({int(g[y, x]) for x, y in comp})})
                    break
    pos = []
    for g in images[:-1]:
        m = (g != avant) & (g != apres)
        petites = [c for c in composantes(m) if len(c) <= PETIT]
        pos.append(_coin(min(petites, key=len)) if len(petites) == 1 else None)
    pas = [p for p in pos if p is not None]
    if len(set(pas)) >= 3:
        dx = [b[0] - a[0] for a, b in zip(pas, pas[1:]) if b != a]
        dy = [b[1] - a[1] for a, b in zip(pas, pas[1:]) if b != a]
        if dx and (all(d > 0 for d in dx) or all(d < 0 for d in dx) or all(d > 0 for d in dy) or all(d < 0 for d in dy)):
            out.append({"sorte": "curseur", "positions": len(set(pas)), "debut": pas[0], "fin": pas[-1]})
    return _uniques_s(out)


def _uniques_s(L):
    vus, out = set(), []
    for x in L:
        if x["sorte"] not in vus or x["sorte"] == "curseur":
            vus.add(x["sorte"])
            out.append(x)
    return out


def evenements(avant, images, clic=None):
    """→ dict des 4 sortes d'événements pour un coup (images = film du coup, la dernière est l'image finale) ; `clic` =
    (x, y) du clic s'il y en a un : un flash qui l'entoure est un `retour_clic` (anneau d'appui), pas un signal du jeu."""
    avant = np.asarray(avant)
    images = [np.asarray(x) for x in images]
    trajs = trajectoires(avant, images)
    tr, masque = transitoires(avant, images)
    cts, rec = contacts(avant, images, trajs) if len(images) > 1 else ([], [])
    sig = signaux(avant, images, masque, trajs, clic) if len(images) > 1 else []
    trajs_pub = [{k: v for k, v in t.items() if not k.startswith("_")} for t in trajs]
    return {"n_images": len(images), "trajectoires": trajs_pub, "transitoires": tr, "contacts": cts, "recolores": rec,
            "signaux": sig}
