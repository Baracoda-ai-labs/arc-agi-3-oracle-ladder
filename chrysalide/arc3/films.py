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
        autres = {frozenset(k) for k in composantes(avant == c) if k != comp}  # objets de même couleur, déjà là
        for g in seq[1:]:
            cands = [k for k in composantes(g == c) if abs(len(k) - len(cur)) <= max(1, len(cur) // 5)
                     and frozenset(k) not in autres]  # un objet resté à sa place n'est pas la suite d'un autre (ft09)
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


# --- CW-445 F2 (E) : ÉVÉNEMENTS TYPÉS, format prudent. L'extracteur DÉCRIT ce qui est visible, il n'interprète pas :
# « pulsation » (une zone change puis revient) et non « échec » ; seule une fin de niveau confirme une victoire.
# Event = dict(kind, frames=(i, j), region=(x0, y0, x1, y1), object_candidates=[(couleur, cases), …] (plusieurs identités
# possibles), displacement=(dx, dy) ou None (seulement si établi par un suivi), pixel_evidence (cases), bord (la région
# touche la bande du bord : interface probable, jauge), revient (l'objet finit où il était), confidence ∈ [0, 1]).
# ActionEvidence = dict(final_state_changed, transient_events_observed, model_predictions_discriminated (None : rempli
# par le modèle qui joue, pas par l'extracteur)). Les images intermédiaires ne deviennent jamais des nœuds du planificateur.
KINDS = ("apparition", "disparition", "deplacement", "recoloration", "chevauchement", "pulsation")


def _region(cases):
    xs, ys = [int(x) for x, _ in cases], [int(y) for _, y in cases]
    return (min(xs), min(ys), max(xs), max(ys))


def _au_bord(region, forme, marge=2):
    x0, y0, x1, y1 = region
    h, w = forme
    return x0 <= marge or y0 <= marge or x1 >= w - 1 - marge or y1 >= h - 1 - marge


def _event(kind, frames, cases, cands, forme, displacement=None, revient=False, confidence=0.5):
    reg = _region(cases)
    dep = None if displacement is None else (int(displacement[0]), int(displacement[1]))
    return {"kind": kind, "frames": (int(frames[0]), int(frames[1])), "region": reg,
            "object_candidates": [(int(c), None if n is None else int(n)) for c, n in cands], "displacement": dep,
            "pixel_evidence": len(cases), "bord": bool(_au_bord(reg, forme)), "revient": bool(revient),
            "confidence": round(confidence, 2)}


def evenements_types(avant, images):
    """→ (liste d'Event, ActionEvidence) pour un coup. Sans état, numpy ; mêmes conventions qu'`evenements`."""
    avant = np.asarray(avant)
    images = [np.asarray(x) for x in images]
    apres, forme, out = images[-1], avant.shape, []
    trajs = trajectoires(avant, images)
    for t in trajs:  # déplacements établis par suivi (même couleur, même taille)
        dep = (t["chemin"][-1][0] - t["chemin"][0][0], t["chemin"][-1][1] - t["chemin"][0][1])
        cases = set().union(*[c for c in t["_cases"] if c])
        out.append(_event("deplacement", (0, len(images)), cases, [(t["couleur"], t["taille"])], forme,
                          displacement=None if t["revient"] else dep, revient=t["revient"],
                          confidence=0.9 if all(c for c in t["_cases"]) else 0.6))
    sillage = np.zeros_like(avant, bool)
    for t in trajs:
        for c in t["_cases"]:
            for x, y in c:
                sillage[y, x] = True
    # changements durables hors sillage : un objet qui n'était pas suivi (multicolore, trop grand) et qui s'est déplacé
    # se voit comme « disparu ici, apparu là » : apparié par motif identique (mêmes couleurs aux mêmes places relatives),
    # il redevient un déplacement établi, et non un faux mécanisme apparition + disparition
    out += _translations_de_couleur(avant, apres, sillage, forme) + _deplacements_par_motif(avant, apres, sillage, forme,
                                                                                            images)
    for t in out:
        if t["kind"] == "deplacement" and "_cases" in t:
            for x, y in t.pop("_cases"):
                sillage[y, x] = True
    # apparition, disparition, recoloration (comparaison avant / après)
    for comp in composantes((avant != apres) & ~sillage):
        c_av = sorted({int(avant[y, x]) for x, y in comp})
        c_ap = sorted({int(apres[y, x]) for x, y in comp})
        fond_av = len(c_av) == 1 and (avant == c_av[0]).sum() > avant.size // 3  # la case était du fond
        fond_ap = len(c_ap) == 1 and (apres == c_ap[0]).sum() > apres.size // 3
        kind = "apparition" if fond_av and not fond_ap else ("disparition" if fond_ap and not fond_av else "recoloration")
        out.append(_event(kind, (0, len(images)), comp, [(c, len(comp)) for c in (c_ap if kind != "disparition" else c_av)],
                          forme, confidence=0.8))
    out = _apparier_par_couleur(out)
    # transitoires hors sillage : pulsation (la zone change puis revient à l'identique)
    for k, g in enumerate(images[:-1]):
        for comp in composantes((g != avant) & (apres == avant) & ~sillage):
            if len(comp) >= 2:
                out.append(_event("pulsation", (k, k + 1), comp, [(int(g[y, x]), len(comp)) for x, y in list(comp)[:1]],
                                  forme, revient=True, confidence=0.7))
    # chevauchement : deux objets suivis qui se recouvrent ou se touchent au milieu du film seulement
    cts, _ = contacts(avant, images, trajs) if len(images) > 1 else ([], [])
    for c in cts:
        ta = next(t for t in trajs if t["couleur"] == c["a"])
        out.append(_event("chevauchement", (c["image"], c["image"] + 1), set().union(*[x for x in ta["_cases"] if x]),
                          [(c["a"], None), (c["b"], None)], forme, confidence=0.5))
    out = _fusionner_pulsations(out)
    preuve = {"final_state_changed": bool((avant != apres).any()),
              "transient_events_observed": any(e["kind"] == "pulsation" or (e["kind"] == "deplacement" and e["revient"])
                                               for e in out) or bool(transitoires(avant, images)[0]["cases"]),
              "model_predictions_discriminated": None}
    return out, preuve


def _translations_de_couleur(avant, apres, sillage, forme):
    """Toutes les cases d'une couleur translatées d'un même vecteur (pièce en diagonale d'un pixel, re86) → déplacement
    établi de cette couleur (confiance 0,7). Le fond (couleur majoritaire) n'est jamais candidat."""
    vals, nb = np.unique(avant, return_counts=True)
    fond = int(vals[nb.argmax()])
    evs = []
    ch = (avant != apres) & ~sillage
    for c in sorted(set(np.unique(avant[ch]).tolist()) & set(np.unique(apres[ch]).tolist()) - {fond}):
        y0, x0 = np.nonzero(avant == c)
        y1, x1 = np.nonzero(apres == c)
        if not len(x0) or not len(x1) or len(x0) > 2000 or abs(len(x0) - len(x1)) > max(3, len(x0) // 10):
            continue
        a_, b_ = set(zip(x0.tolist(), y0.tolist())), set(zip(x1.tolist(), y1.tolist()))
        if len(a_ & b_) > 0.5 * len(a_):  # la couleur est restée en place pour l'essentiel : des cases ont basculé sur
            continue                     # une grille régulière (ft09), ce n'est pas un objet qui s'est déplacé
        cx, cy = round(x1.mean() - x0.mean()), round(y1.mean() - y0.mean())
        # vecteur qui recouvre le mieux ; ≥ 90 % des cases (une case cachée par un marqueur ou une autre pièce, re86)
        d, rec = max((((cx + i, cy + j), len({(x + cx + i, y + cy + j) for x, y in a_} & b_))
                      for i in (-1, 0, 1) for j in (-1, 0, 1)), key=lambda t: t[1])
        if d != (0, 0) and rec >= 0.9 * max(len(a_), len(b_)):
            cases = a_ | b_
            e = _event("deplacement", (0, 1), cases, [(int(c), len(a_))], forme, displacement=d,
                       confidence=0.7 if rec == len(a_) == len(b_) else 0.6)
            e["_cases"] = cases
            evs.append(e)
    return evs


def _deplacements_par_motif(avant, apres, sillage, forme, images=()):
    """Objets (composantes 4-connexes de cases non-fond, toutes couleurs) disparus d'un endroit et réapparus ailleurs avec
    exactement le même motif de couleurs. Déplacement ÉTABLI (confiance 0,7) seulement si le film montre le motif en
    chemin (une position intermédiaire sur le segment) ; sinon NON établi (displacement None, 0,4) : sans film, « une case
    s'éteint ici, une autre s'allume là » (ft09) ressemble exactement à un saut."""
    vals, nb = np.unique(avant, return_counts=True)
    fond = int(vals[nb.argmax()])
    ch = (avant != apres) & ~sillage

    def objets(g):
        out = []
        for comp in composantes((g != fond) & ch):
            x0, y0 = min(x for x, _ in comp), min(y for _, y in comp)
            out.append((frozenset((x - x0, y - y0, int(g[y, x])) for x, y in comp), (x0, y0), comp))
        return out
    partis, arrives, evs = objets(avant), objets(apres), []
    libres = list(arrives)
    for motif, (x0, y0), comp in partis:
        if len(comp) < TAILLE_MIN:
            continue
        m = [a for a in libres if a[0] == motif and a[1] != (x0, y0)]
        if not m:
            continue
        cible = min(m, key=lambda a: abs(a[1][0] - x0) + abs(a[1][1] - y0))
        libres.remove(cible)
        d = (cible[1][0] - x0, cible[1][1] - y0)
        vu = _motif_en_chemin(motif, (x0, y0), d, images[:-1])
        e = _event("deplacement", (0, 1), comp | cible[2], [(c, len(comp)) for c in sorted({v[2] for v in motif})[:3]],
                   forme, displacement=d if vu else None, confidence=0.7 if vu else 0.4)
        e["_cases"] = comp | cible[2]
        evs.append(e)
    return evs


def _apparier_par_couleur(evs):
    """Dans un même coup, une couleur qui disparaît ici et apparaît là en quantités voisines (± 10 %) : un seul
    déplacement NON établi (displacement None, confiance 0,4), et non deux mécanismes (apparition + disparition)."""
    from collections import defaultdict
    par = defaultdict(lambda: {"apparition": [], "disparition": []})
    for e in evs:
        if e["kind"] in ("apparition", "disparition") and len(e["object_candidates"]) == 1:
            par[e["object_candidates"][0][0]][e["kind"]].append(e)
    retirer = set()
    nouveaux = []
    for c, d in par.items():
        na = sum(e["pixel_evidence"] for e in d["apparition"])
        nd = sum(e["pixel_evidence"] for e in d["disparition"])
        if na and nd and abs(na - nd) <= max(1, max(na, nd) // 10):
            grp = d["apparition"] + d["disparition"]
            retirer |= {id(e) for e in grp}
            x0 = min(e["region"][0] for e in grp)
            y0 = min(e["region"][1] for e in grp)
            x1 = max(e["region"][2] for e in grp)
            y1 = max(e["region"][3] for e in grp)
            nouveaux.append({"kind": "deplacement", "frames": grp[0]["frames"], "region": (x0, y0, x1, y1),
                             "object_candidates": [(c, nd)], "displacement": None, "pixel_evidence": na + nd,
                             "bord": all(e["bord"] for e in grp), "revient": False, "confidence": 0.4})
    return [e for e in evs if id(e) not in retirer] + nouveaux


def _motif_en_chemin(motif, depart, d, intermediaires):
    """Le motif apparaît-il, dans une image intermédiaire du film, à une position strictement entre départ et arrivée ?"""
    n = max(abs(d[0]), abs(d[1]))
    for g in intermediaires:
        for k in range(1, n):
            ox, oy = depart[0] + round(d[0] * k / n), depart[1] + round(d[1] * k / n)
            if all(0 <= oy + dy < g.shape[0] and 0 <= ox + dx < g.shape[1] and int(g[oy + dy, ox + dx]) == c
                   for dx, dy, c in motif):
                return True
    return False


def _fusionner_pulsations(evs):
    """Une même région qui pulse sur plusieurs images = un seul événement (frames étendues)."""
    out, vus = [], {}
    for e in evs:
        if e["kind"] != "pulsation":
            out.append(e)
            continue
        k = e["region"]
        if k in vus:
            vus[k]["frames"] = (vus[k]["frames"][0], e["frames"][1])
        else:
            vus[k] = e
            out.append(e)
    return out


# --- CW-449 / CW-455 (E) : OBJET CONTRÔLÉ candidat, depuis les coups joués (sans vérité). Pour T1 (MoteurC dans P1).
SENS_FLECHES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}


def candidat_controle(coups, n_min=3, accord_min=0.7):
    """`coups` = [(action, avant, film)], action ∈ 1..5 ou ("clic", x, y). → [{couleur, coups, accord}] trié (meilleur
    d'abord) : couleurs dont les déplacements ÉTABLIS (hors bord) vont dans le sens de la flèche dans ≥ `accord_min` des
    coups fléchés où elles bougent, sur ≥ `n_min` coups. Flèches seulement : le clic est retiré (0/2 contre les programmes
    exacts, CCM-086-E). Vérifié 5/5 contre les programmes exacts (CCM-086-E) ; contrôles négatifs ft09, lp85 : rien."""
    fl = {}
    for a, avant, film in coups:
        if not (isinstance(a, int) and a in SENS_FLECHES):
            continue
        sx, sy = SENS_FLECHES[a]
        evs, _ = evenements_types(avant, film)
        for e in evs:
            if e["kind"] != "deplacement" or e["displacement"] is None or e["bord"] or not e["object_candidates"]:
                continue
            c = e["object_candidates"][0][0]
            dx, dy = e["displacement"]
            n, ok = fl.get(c, (0, 0))
            fl[c] = (n + 1, ok + ((dx * sx + dy * sy) > 0))
    out = [{"couleur": c, "coups": n, "accord": round(ok / n, 2)} for c, (n, ok) in fl.items()
           if n >= n_min and ok / n >= accord_min]
    return sorted(out, key=lambda x: (-x["accord"], -x["coups"]))
