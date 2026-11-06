# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — des images 64×64 aux faits logiques au niveau objets (CW-067.1).
Rendu inverse simple en attendant celui de A (CW-068) : taille de case et décalage déduits des images (blocs uniformes),
objets = composantes 4-connexes d'une même couleur hors fond, barres de jauge retirées par le masque de B (lecture seule).
Un état est un tuple trié d'objets (couleur, forme, x, y) ; la forme est l'ensemble des cases relatives au coin haut-gauche."""
import os
from collections import Counter
from itertools import pairwise, permutations

import numpy as np

from chrysalide.arc3.masque import Masque


def echelle(grilles, seuil=0.85):
    """(s, ox, oy) le plus grossier tel que presque tous les blocs s×s soient uniformes sur toutes les images.
    Échelle entière (Camera arcengine) ; les blocs qui touchent les lignes/colonnes 0 et 63 (jauges) ne comptent pas.
    (Le letterbox centré n'est pas imposé : ls20 et sb26 ne le respectent pas.)"""
    gs = [np.asarray(grilles[i]) for i in sorted({0, len(grilles) // 2, len(grilles) - 1})]  # 3 images suffisent
    for s in range(21, 0, -1):
        for oy in range(s):
            for ox in range(s):
                ny, nx = (64 - oy) // s, (64 - ox) // s
                if ny < 3 or nx < 3:
                    continue
                uni = tot = 0
                for g in gs:
                    b = g[oy:oy + ny * s, ox:ox + nx * s].reshape(ny, s, nx, s)
                    m = (b == b[:, :1, :, :1]).all(axis=(1, 3))
                    r0, r1 = int(oy == 0), ny - int(oy + ny * s >= 64)
                    c0, c1 = int(ox == 0), nx - int(ox + nx * s >= 64)
                    m = m[r0:r1, c0:c1]
                    uni, tot = uni + int(m.sum()), tot + m.size
                if tot and uni >= seuil * tot:
                    return s, ox, oy
    return 1, 0, 0


def echelle_par_objets(grilles, seuil=0.95):
    """C (CW-254, CCM-169/171-B : r11l, lp85) : (s, ox, oy) le plus grossier tel que, sur la 1re image, presque tous les
    OBJETS (composantes d'une couleur au pixel, hors bords 0 et 63) restent INTACTS : chaque bloc s×s qu'ils touchent est
    uni. Une perte sur le fond ou les bords est tolérée, pas sur un objet (anneau de r11l, cadre creux de lp85)."""
    g = np.asarray(grilles[0])
    fond = int(np.bincount(g.ravel()).argmax())
    objs = [o for o in objets(g, fond) if not any(x in (0, 63) or y in (0, 63) for x, y in cellules(o))]
    if not objs:
        return echelle(grilles[:1])
    for s in range(21, 1, -1):
        for oy in range(s):
            for ox in range(s):
                ny, nx = (64 - oy) // s, (64 - ox) // s
                if ny < 3 or nx < 3:
                    continue
                b = g[oy:oy + ny * s, ox:ox + nx * s].reshape(ny, s, nx, s)
                uni = (b == b[:, :1, :, :1]).all(axis=(1, 3))
                ok = 0
                for o in objs:
                    blocs = {((y - oy) // s, (x - ox) // s) for x, y in cellules(o)}
                    ok += all(0 <= by < ny and 0 <= bx < nx and uni[by, bx] for by, bx in blocs)
                if ok >= seuil * len(objs):
                    return s, ox, oy
    return 1, 0, 0


def echelle_objets(grilles, seuil=0.85, seuil_objets=0.6):
    """Comme `echelle`, mais l'uniformité est AUSSI exigée sur les blocs qui contiennent des pixels hors fond (≥
    `seuil_objets`) : le fond uni ne suffit plus à faire passer une échelle trop grossière qui avale les objets (sp80 :
    14 au lieu de 4, banc de perception CCM-045-C)."""
    gs = [np.asarray(grilles[i]) for i in sorted({0, len(grilles) // 2, len(grilles) - 1})]
    fonds = [int(np.bincount(g.ravel()).argmax()) for g in gs]
    for s in range(21, 0, -1):
        for oy in range(s):
            for ox in range(s):
                ny, nx = (64 - oy) // s, (64 - ox) // s
                if ny < 3 or nx < 3:
                    continue
                uni = tot = uo = to = 0
                for g, f in zip(gs, fonds, strict=True):
                    b = g[oy:oy + ny * s, ox:ox + nx * s].reshape(ny, s, nx, s)
                    m = (b == b[:, :1, :, :1]).all(axis=(1, 3))
                    o = (b != f).any(axis=(1, 3))
                    r0, r1 = int(oy == 0), ny - int(oy + ny * s >= 64)
                    c0, c1 = int(ox == 0), nx - int(ox + nx * s >= 64)
                    m, o = m[r0:r1, c0:c1], o[r0:r1, c0:c1]
                    uni, tot = uni + int(m.sum()), tot + m.size
                    uo, to = uo + int((m & o).sum()), to + int(o.sum())
                if tot and uni >= seuil * tot and (s == 1 or (to and uo >= seuil_objets * to)):
                    return s, ox, oy
    return 1, 0, 0


def echelle_candidats(grilles, seuil=0.85):
    """Échelles plausibles : la plus grossière au-dessus du seuil (celle d'`echelle`) et celle d'uniformité maximale
    (s ≥ 2). Une seule image ne tranche pas toujours (A, CCM-064-A) : c'est le rejeu exact qui départage."""
    gs = [np.asarray(grilles[i]) for i in sorted({0, len(grilles) // 2, len(grilles) - 1})]
    best, premier = None, None
    for s in range(21, 1, -1):
        for oy in range(s):
            for ox in range(s):
                ny, nx = (64 - oy) // s, (64 - ox) // s
                if ny < 3 or nx < 3:
                    continue
                uni = tot = 0
                for g in gs:
                    b = g[oy:oy + ny * s, ox:ox + nx * s].reshape(ny, s, nx, s)
                    m = (b == b[:, :1, :, :1]).all(axis=(1, 3))
                    r0, r1 = int(oy == 0), ny - int(oy + ny * s >= 64)
                    c0, c1 = int(ox == 0), nx - int(ox + nx * s >= 64)
                    m = m[r0:r1, c0:c1]
                    uni, tot = uni + int(m.sum()), tot + m.size
                u = uni / tot if tot else 0
                if u >= seuil and premier is None:
                    premier = (s, ox, oy)
                if best is None or u > best[0] + 1e-9:
                    best = (u, (s, ox, oy))
    out = [premier or echelle(grilles)]
    if best and best[0] >= seuil and best[1] not in out:
        out.append(best[1])
    eo = echelle_objets(grilles, seuil)  # banc de perception (CCM-046-C) : ni l'une ni l'autre ne gagne partout
    if eo not in out:
        out.append(eo)
    return out


_CASES_TF = {}  # D (CCM-261-B : TRAITS_FINS −7,6 % de coups) : chaque tour relit TOUT l'historique ; même image → même résultat


def cases(g, s, ox, oy):
    if s > 1 and os.environ.get("CHRYS_TRAITS_FINS") == "1":
        cle = (id(g), s, ox, oy)  # même objet image d'un tour à l'autre ; contenu revérifié (copie gardée), donc sûr
        e = _CASES_TF.get(cle)
        g = np.asarray(g)
        if e is None or e[0].shape != g.shape or not np.array_equal(e[0], g):
            if len(_CASES_TF) > 50000:
                _CASES_TF.clear()
            e = _CASES_TF[cle] = (g.copy(), _cases(g, s, ox, oy))
        return e[1].copy()
    return _cases(np.asarray(g), s, ox, oy)


def _cases(g, s, ox, oy):
    ny, nx = (64 - oy) // s, (64 - ox) // s
    c = g[oy:oy + ny * s:s, ox:ox + nx * s:s]
    if s > 1 and os.environ.get("CHRYS_TRAITS_FINS") == "1":
        # D (CCM-206-C, g50t : la sortie est un cadre d'un pixel avec un point central d'un pixel, dans un couloir, perdus
        # à l'échelle 2) : un bloc MIXTE (rares : l'échelle est choisie pour que ≥ 85 % des blocs soient uniformes) prend
        # sa couleur MINORITAIRE (le trait, le point) ; à égalité, le pixel haut-gauche reste
        b = g[oy:oy + ny * s, ox:ox + nx * s].reshape(ny, s, nx, s).transpose(0, 2, 1, 3).reshape(ny, nx, s * s)
        # (C, CCM-211-C : sinon le bord multicolore du JOUEUR prend la couleur de la sortie) seulement quand la couleur
        # majoritaire du bloc est celle de la RÉGION autour : parmi les 8 blocs voisins, les UNIFORMES (au moins un) sont
        # tous de cette couleur (les voisins mixtes, autres morceaux du même trait, sont ignorés)
        uni = (b == b[..., :1]).all(axis=2)
        ys, xs = np.nonzero(~uni)
        if len(ys):  # vectorisé (CW-349.5 : la boucle par bloc coûtait ≈ 1 ms par image)
            sub = b[ys, xs]                                          # m × k pixels des blocs mixtes
            cnt = (sub[:, :, None] == sub[:, None, :]).sum(axis=2)   # pour chaque pixel, nombre de pixels de sa couleur
            nette = cnt.min(axis=1) < cnt.max(axis=1)                # pas d'égalité
            grand = np.iinfo(np.int64).max  # à égalité de compte : la plus petite couleur (comme np.unique)
            s64 = sub.astype(np.int64)
            maj = np.where(cnt == cnt.max(axis=1)[:, None], s64, grand).min(axis=1)
            mino = np.where(cnt == cnt.min(axis=1)[:, None], s64, grand).min(axis=1)
            pu = np.pad(uni, 1, constant_values=False)
            pc = np.pad(c.astype(np.int64), 1, constant_values=-1)
            ok_u, tout = np.zeros(len(ys), bool), np.ones(len(ys), bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    u = pu[ys + 1 + dy, xs + 1 + dx]
                    ok_u |= u
                    tout &= ~u | (pc[ys + 1 + dy, xs + 1 + dx] == maj)
            garder = nette & ok_u & tout & (cnt.min(axis=1) <= 4)  # ≤ 4 pixels minoritaires : sinon pas un point
            if garder.any():  # (B, CCM-252-B : trop d'objets en plus → induction plus lente) seulement les blocs dont le
                # trait appartient à une PETITE composante (≤ 4 pixels) qui a DISPARU à la réduction (aucune case ne la montre)
                from scipy.ndimage import label
                G = g[oy:oy + ny * s, ox:ox + nx * s]
                for m in np.unique(mino[garder]):
                    lab, _ = label(G == m, structure=np.ones((3, 3)))  # 8-connexité : une diagonale = un seul trait
                    vis = set(np.unique(lab[::s, ::s][c == m]).tolist()) - {0}
                    taille = np.bincount(lab.ravel())
                    idx = np.nonzero(garder & (mino == m))[0]
                    k = np.argmax(sub[idx] == m, axis=1)  # 1er pixel de couleur m dans le bloc
                    py, px = ys[idx] * s + k // s, xs[idx] * s + k % s
                    lp = lab[py, px]  # une PETITE composante disparue (≤ 4 pixels : un point, pas un détail de sprite)
                    garder[idx[np.isin(lp, list(vis)) | (taille[lp] > 4)]] = False
            if garder.any():
                c = c.copy()
                c[ys[garder], xs[garder]] = mino[garder]
    return c


def masque_cases(grilles, s, ox, oy):
    """Cases (r, c) couvertes par une barre de jauge selon le masque de B, appris sur la trajectoire."""
    m = Masque(court=os.environ.get("CHRYS_JAUGE_COURTE", "0") == "1")  # D (CW-215) : jauge des niveaux < 8 coups
    ls = [np.asarray(g).tolist() for g in grilles]
    for a, b in pairwise(ls):
        m.observer(a, b)
    return {((r - oy) // s, (c - ox) // s) for r, c in m.cellules() if r >= oy and c >= ox}


def couleurs_diagonales(c, fond, exclues=frozenset()):
    """C (re86 N2 ; CHRYS_DIAGONALES=1) : couleurs dont des composantes 4-connexes d'UNE case se touchent par un coin
    (lignes diagonales) : elles seront découpées en 8-connexité. re86 N5 : la couleur d'un losange tracé en diagonale a
    aussi un carré plein ailleurs (légende) ; seules ses cases isolées comptent (avant : toutes les composantes d'une
    case exigées, et le losange restait 44 objets d'un pixel)."""
    c = np.asarray(c)
    res = set()
    for col in set(np.unique(c).tolist()) - {fond}:
        ys, xs = np.nonzero(c == col)
        cs = {(int(y), int(x)) for y, x in zip(ys, xs, strict=True)} - set(exclues)
        seules = {(y, x) for y, x in cs if not any((y + dy, x + dx) in cs for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)))}
        if len(seules) >= 2 and any((y + 1, x + d) in seules for y, x in seules for d in (-1, 1)):
            res.add(int(col))
    return frozenset(res)


def objets(c, fond=None, exclues=frozenset(), diagonales=frozenset()):
    """Composantes 4-connexes d'une couleur (8-connexes pour les couleurs `diagonales`) ; renvoie un tuple trié de
    (couleur, forme, x, y)."""
    c = np.asarray(c)
    if fond is None:
        fond = Counter(c.ravel().tolist()).most_common(1)[0][0]
    vu, res = set(exclues), []
    h, w = c.shape
    for r in range(h):
        for q in range(w):
            if (r, q) in vu or c[r, q] == fond:
                continue
            col, pile, comp = c[r, q], [(r, q)], []
            vu.add((r, q))
            while pile:
                y, x = pile.pop()
                comp.append((y, x))
                voisins = ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1))
                if col in diagonales:
                    voisins += ((y + 1, x + 1), (y + 1, x - 1), (y - 1, x + 1), (y - 1, x - 1))
                for y2, x2 in voisins:
                    if 0 <= y2 < h and 0 <= x2 < w and (y2, x2) not in vu and c[y2, x2] == col:
                        vu.add((y2, x2))
                        pile.append((y2, x2))
            y0, x0 = min(y for y, _ in comp), min(x for _, x in comp)
            res.append((int(col), frozenset((x - x0, y - y0) for y, x in comp), x0, y0))
    return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))


MARQUEUR = 512  # code des marqueurs recollés : 512 + couleur (rendu : code % 16 ; trié après l'hôte → dessiné dessus)


def recoller_marqueurs(e, couleurs=None, diagonales=frozenset()):
    """C (CCM-102-C, re86 ; CHRYS_MARQUEUR=1) : un MARQUEUR est un objet d'une case dont les 4 voisines sont couvertes
    par ≥ 2 objets distincts d'une même autre couleur (il coupe un objet en morceaux : croix sélectionnée de re86). Les
    morceaux sont recollés en UN objet de leur couleur, case du marqueur comprise (complétion amodale) ; le marqueur
    devient une classe propre (MARQUEUR + couleur), posée par-dessus. L'appariement et les lois de l'hôte restent ainsi
    les mêmes, qu'il soit sélectionné ou non. Hors de ce motif, l'état est rendu inchangé."""
    occ = {}
    for i, o in enumerate(e):
        for c in cellules(o):
            occ[c] = i
    fusion, marques = {}, {}
    for i, o in enumerate(e):
        if len(o[1]) != 1 or o[0] >= MARQUEUR or (couleurs is not None and o[0] not in couleurs):
            continue
        x, y = o[2], o[3]
        par_couleur = {}
        voisins = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        # C (re86 N5, CHRYS_DIAGONALES=1) : centre d'un X tracé en diagonale ; les 4 voisines en coin sont couvertes par
        # des bras (objets de plus d'une case) d'une même couleur, les 4 voisines droites sont libres
        if diagonales and not any(v in occ for v in voisins):
            coins = [occ.get((x + a, y + b)) for a in (-1, 1) for b in (-1, 1)]
            if all(j is not None and len(e[j][1]) > 1 and e[j][0] in diagonales for j in coins):
                voisins = tuple((x + a, y + b) for a in (-1, 1) for b in (-1, 1))
        for v in voisins:
            j = occ.get(v)
            if j is None or e[j][0] == o[0]:
                break
            par_couleur.setdefault(e[j][0], set()).add(j)
        else:
            morceaux = next(iter(par_couleur.values())) if len(par_couleur) == 1 else set()
            # ≥ 2 morceaux coupés, ou un seul hôte qui couvre déjà la case du marqueur (recollé par CHRYS_AMODAL)
            entier = len(morceaux) == 1 and (x, y) in cellules(e[next(iter(morceaux))])
            if (len(morceaux) >= 2 or entier) and not morceaux & set(fusion):
                for j in morceaux:
                    fusion[j] = i
                marques[i] = morceaux
    seuls = set()
    if couleurs is not None and os.environ.get("CHRYS_PORTEUR_BOITE") == "1":  # C (re86 N5) : marqueur au centre VIDE
        boites = [(min(x for x, _ in cs), min(y for _, y in cs), max(x for x, _ in cs), max(y for _, y in cs))
                  for cs in (cellules(o) for o in e if len(o[1]) > 1 and o[0] < MARQUEUR)]  # d'une pièce creuse : marqueur
        seuls = {i for i, o in enumerate(e) if i not in marques and len(o[1]) == 1 and o[0] in couleurs  # sans recollage
                 and any(b[0] < o[2] < b[2] and b[1] < o[3] < b[3] for b in boites)}
    if not marques and not seuls:
        return e
    res = [o for k, o in enumerate(e) if k not in fusion and k not in marques and k not in seuls]
    res += [(MARQUEUR + e[i][0], e[i][1], e[i][2], e[i][3]) for i in seuls]
    for i, morceaux in marques.items():
        m = e[i]
        cs = set().union(*[cellules(e[j]) for j in morceaux]) | {(m[2], m[3])}
        x0, y0 = min(x for x, _ in cs), min(y for _, y in cs)
        res.append((e[next(iter(morceaux))][0], frozenset((x - x0, y - y0) for x, y in cs), x0, y0))
        res.append((MARQUEUR + m[0], m[1], m[2], m[3]))
    return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))


def cellules(o):
    return {(o[2] + dx, o[3] + dy) for dx, dy in o[1]}


def grille_tuiles(cs, exclues=frozenset(), actions=None):
    """Grille de tuiles d'un jeu à cases : chaque transition change des rectangles pleins ; s'il en est au moins 2 de même
    taille (h, l) > 1 case, pas = pgcd des écarts entre leurs coins (sinon la taille). → (couleurs, y0, x0, py, px, h, l)
    ou None. Couleurs = celles qui apparaissent dans ces rectangles, avant ou après. Seules les transitions dues à un CLIC
    comptent (`actions` donné) : un mobile qui se déplace change aussi des rectangles (cases quittées et atteintes)."""
    from math import gcd
    rects, couleurs = [], set()
    for t, (a, b) in enumerate(pairwise(cs)):
        if actions is not None and not isinstance(actions[t], tuple):
            continue
        a, b = np.asarray(a), np.asarray(b)
        ch = {(int(r), int(c)) for r, c in zip(*np.nonzero(a != b), strict=True)} - set(exclues)
        while ch:
            pile, comp = [ch.pop()], []
            while pile:
                r, c = pile.pop()
                comp.append((r, c))
                for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if q in ch:
                        ch.remove(q)
                        pile.append(q)
            r0, c0 = min(r for r, _ in comp), min(c for _, c in comp)
            h, w = max(r for r, _ in comp) - r0 + 1, max(c for _, c in comp) - c0 + 1
            if len(comp) == h * w > 1:
                rects.append((r0, c0, h, w))
                couleurs |= {int(a[r, c]) for r, c in comp} | {int(b[r, c]) for r, c in comp}
    if not rects:
        return None
    (h, w), n = Counter((r[2], r[3]) for r in rects).most_common(1)[0]
    rs = [r for r in rects if (r[2], r[3]) == (h, w)]
    if n < 2:
        return None
    py = px = 0
    for r in rs:
        py, px = gcd(py, r[0] - rs[0][0]), gcd(px, r[1] - rs[0][1])
    py, px = (max(py, h)), (max(px, w))
    return frozenset(couleurs), rs[0][0] % py, rs[0][1] % px, py, px, h, w


def decouper_tuiles(e, t):
    """Objets des couleurs de la grille de tuiles découpés tuile par tuile ; le reste d'un objet (liseré) garde sa forme."""
    if not t:
        return e
    couleurs, y0, x0, py, px, h, w = t
    res = []
    for o in e:
        if o[0] not in couleurs:
            res.append(o)
            continue
        groupes = {}
        for x, y in cellules(o):
            dy, dx = (y - y0) % py, (x - x0) % px
            k = ((y - y0) // py, (x - x0) // px) if dy < h and dx < w else None
            groupes.setdefault(k, []).append((x, y))
        for cs_ in groupes.values():
            gx, gy = min(x for x, _ in cs_), min(y for _, y in cs_)
            res.append((o[0], frozenset((x - gx, y - gy) for x, y in cs_), gx, gy))
    return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))


def formes_mobiles(etats):
    """{(couleur, forme): code} pour les formes qui bougent (appariées d'une image à l'autre, déplacement ≠ 0) d'une
    couleur qui a AUSSI des objets d'une autre forme jamais déplacés ; forme persistante (même nombre sur toutes les
    images) qui se déplace sur au moins 2 transitions (CW-240 : sinon ar25 perdait son mobile). Code = couleur + 16·(rang du 1er déplacement de la forme + 1) + 256 :
    distinct des codes de `details` (< 256), rendu dans sa vraie couleur (code mod 16)."""
    bouge, toutes = {}, {}  # (couleur, forme) → rang du 1er déplacement (stable quand on ajoute des images, CCM-089-C)
    nb_dep = Counter()  # (couleur, forme) → transitions où elle se déplace
    ensemble = set()  # paires de (couleur, forme) de même couleur déplacées au MÊME coup (C, CHRYS_FORMES_SEL)
    for e in etats:
        for o in e:
            toutes.setdefault(o[0], set()).add(o[1])
    # forme PERSISTANTE (CW-240, ar25) : présente en même nombre sur TOUTES les images ; sinon (forme qui change par
    # reflet, occultation, rotation), l'objet changerait de classe d'une image à l'autre et casserait les lois apprises
    comptes = [Counter((o[0], o[1]) for o in e) for e in etats]
    persistantes = {k for k in comptes[0] if all(c_[k] == comptes[0][k] for c_ in comptes)} if comptes else set()
    if os.environ.get("CHRYS_FORMES_SEL", "1") == "1" and comptes:  # C (ar25 N4) : deux pièces de même couleur qui se
        par_c = [Counter(o[0] for o in e) for e in etats]                # touchent fusionnent ; la persistance n'est jugée
        persistantes |= {k for k in comptes[0] if all(                  # que sur les images où la couleur garde son
            c_[k] == comptes[0][k] for c_, pc in zip(comptes, par_c) if pc[k[0]] == par_c[0][k[0]])}  # nombre d'objets
    for e0, e1 in pairwise(etats):
        paires, _ = apparier(e0, e1)
        n0, n1 = Counter((o[0], o[1]) for o in e0), Counter((o[0], o[1]) for o in e1)
        # déplacement vrai : même nombre d'objets de la classe avant et après (sinon apparition / bascule de couleur)
        ce_coup = set()
        for i, j in paires:
            k = (e0[i][0], e0[i][1])
            if j is not None and (e0[i][2], e0[i][3]) != (e1[j][2], e1[j][3]) and n0[k] == n1[k]:
                nb_dep[k] += 1
                ce_coup.add(k)
                if k not in bouge:
                    bouge[k] = len(bouge)
        ensemble |= {(a, b) for a in ce_coup for b in ce_coup if a != b and a[0] == b[0]}
    bouge = {k: r for k, r in bouge.items() if k in persistantes and nb_dep[k] >= 2}  # bouge ensemble, ≥ 2 transitions
    out = {}
    for c, fs in toutes.items():
        mob = sorted((f for f in fs if (c, f) in bouge), key=lambda f, c=c: bouge[(c, f)])
        # C (ar25 N4, CHRYS_FORMES_SEL) : aussi quand TOUTES les formes bougent, mais jamais deux au même coup (une
        # pièce sélectionnée à la fois) : chaque forme mobile reçoit sa classe
        sel = (os.environ.get("CHRYS_FORMES_SEL", "1") == "1" and len(mob) >= 2
               and not any((c, f) in {a for a, _ in ensemble} for f in mob))
        if mob and (len(mob) < len(fs) or sel) and c < 16:
            out.update({(c, f): 256 + c + 16 * (k + 1) for k, f in enumerate(mob)})
    return out


def reclasser_formes(e, fm):
    if not fm:
        return e
    res = [((fm.get((o[0], o[1]), o[0])), o[1], o[2], o[3]) for o in e]
    return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))


def _chaines(etats):
    """Identité de chaque objet d'image en image (apparier : même couleur et forme, déplacement minimal).
    → ids[t][i] = identifiant de l'objet i de l'image t."""
    ids, n = [list(range(len(etats[0])))] if etats else [], len(etats[0]) if etats else 0
    for t, (e0, e1) in enumerate(pairwise(etats)):
        cur = [None] * len(e1)
        paires, _ = apparier(e0, e1)
        for i, j in paires:
            if j is not None:
                cur[j] = ids[t][i]
        for j in range(len(e1)):
            if cur[j] is None:
                cur[j], n = n, n + 1
        ids.append(cur)
    return ids


def identites(etats, portee=2):
    """Identité PERSISTANTE (CW-249, action 3) : d'abord `apparier` (même couleur et forme, déplacement minimal) ; puis
    les objets restés seuls sont appariés sans regarder leur apparence, par cases communes (le plus grand recouvrement),
    sinon par centre à au plus `portee` cases. Un objet garde donc son identité quand il change de couleur (bascule,
    interrupteur) ou de forme (rotation). → (ids, changements) : ids[t][i] comme `_chaines` ; changements = [(t, id,
    (couleur, forme) avant, (couleur, forme) après)] pour chaque objet apparié dont l'apparence a changé entre t et t+1."""
    if not etats:
        return [], []

    def centre(o):
        cs = cellules(o)
        return sum(x for x, _ in cs) / len(cs), sum(y for _, y in cs) / len(cs)
    ids, n, chg = [list(range(len(etats[0])))], len(etats[0]), []
    for t, (e0, e1) in enumerate(pairwise(etats)):
        cur = [None] * len(e1)
        paires, _ = apparier(e0, e1)
        pris = set()
        for i, j in paires:
            if j is not None:
                cur[j] = ids[t][i]
                pris.add(i)
        seuls0 = [i for i in range(len(e0)) if i not in pris]
        seuls1 = [j for j in range(len(e1)) if cur[j] is None]
        cand = []
        for i in seuls0:
            c0, ci = cellules(e0[i]), centre(e0[i])
            for j in seuls1:
                rec = len(c0 & cellules(e1[j]))
                cj = centre(e1[j])
                d = abs(ci[0] - cj[0]) + abs(ci[1] - cj[1])
                if rec or d <= portee:
                    cand.append((-rec, d, i, j))
        utilises0 = set()
        for _r, _d, i, j in sorted(cand):
            if i in utilises0 or cur[j] is not None:
                continue
            cur[j] = ids[t][i]
            utilises0.add(i)
            if (e0[i][0], e0[i][1]) != (e1[j][0], e1[j][1]):
                chg.append((t, ids[t][i], (e0[i][0], e0[i][1]), (e1[j][0], e1[j][1])))
        # D (CCM-180-B, ar25 : objet en partie caché dont la partie visible saute) : s'il reste UN SEUL objet orphelin
        # d'une couleur avant et UN SEUL après, c'est le même objet, quelle que soit la distance
        r0 = [i for i in seuls0 if i not in utilises0]
        r1 = [j for j in range(len(e1)) if cur[j] is None]
        for col in {e0[i][0] for i in r0}:
            a0 = [i for i in r0 if e0[i][0] == col]
            a1 = [j for j in r1 if e1[j][0] == col]
            if len(a0) == 1 and len(a1) == 1:
                cur[a1[0]] = ids[t][a0[0]]
                if e0[a0[0]][1] != e1[a1[0]][1]:
                    chg.append((t, ids[t][a0[0]], (col, e0[a0[0]][1]), (col, e1[a1[0]][1])))
        for j in range(len(e1)):
            if cur[j] is None:
                cur[j], n = n, n + 1
        ids.append(cur)
    return ids, chg


def comportements(etats, actions, sauf=frozenset()):
    """Classes par comportement (CHRYS_COMPORTEMENT) : pour chaque (couleur, forme) à plusieurs objets, le déplacement
    de chaque objet sous chaque action (flèches, SPACE) ; deux objets en conflit (même action, deux déplacements NON NULS
    différents) sont mis dans des groupes distincts ; au plus 6 objets par (couleur, forme), couleurs atomiques exclues. Groupe 0 = couleur d'origine ; groupe k ≥ 1 = 512 + c + 16·k (rendu
    dans sa couleur, code mod 16). Aucun conflit = états inchangés (F-C2)."""
    if len(etats) < 2:
        return etats, {}
    ids = _chaines(etats)
    dep, cle = {}, {}  # id → {action: {déplacements}} ; id → (couleur, forme)
    for t, (e0, e1) in enumerate(pairwise(etats)):
        a = actions[t]
        if isinstance(a, tuple):
            continue
        pos1 = {ids[t + 1][j]: (o[2], o[3]) for j, o in enumerate(e1)}
        for i, o in enumerate(e0):
            k = ids[t][i]
            cle[k] = (o[0], o[1])
            if k in pos1:
                dep.setdefault(k, {}).setdefault(a, set()).add((pos1[k][0] - o[2], pos1[k][1] - o[3]))
    groupes = {}
    for k, ck in cle.items():
        groupes.setdefault(ck, []).append(k)
    code = {}
    for (c, _f), ks in groupes.items():
        if len(ks) < 2 or len(ks) > 6 or c >= 16 or c in sauf:  # pas les couleurs atomiques ni les foules (sc25)
            continue
        parts = []  # [(signature fusionnée, [ids])]
        for k in sorted(ks):
            sig = dep.get(k, {})
            for sp, membres in parts:
                # conflit = les deux BOUGENT sous la même action, avec des déplacements différents (miroir de m0r0) ;
                # « l'un bouge, l'autre non » n'en est pas un (y007 : une caisse poussée, l'autre immobile, même règle)
                if all(sp[a] == v or (0, 0) in sp[a] | v for a, v in sig.items() if a in sp and len(v) == 1 and len(sp[a]) == 1):
                    for a, v in sig.items():
                        sp.setdefault(a, set()).update(v)
                    membres.append(k)
                    break
            else:
                parts.append(({a: set(v) for a, v in sig.items()}, [k]))
        if len(parts) == 1 and os.environ.get("CHRYS_IMMOBILE", "1") == "1":
            # C (ka59 N4, CCM-044-E) : un objet PILOTÉ (il bouge sous au moins la moitié des flèches jouées) et un jumeau
            # qui ne bouge JAMAIS sont deux classes (le jumeau est une cible, pas une 2e pièce) ; une caisse poussée de
            # temps en temps (y007) ne compte pas comme pilotée
            def nb(k, bouge):
                return sum(1 for a, v in dep.get(k, {}).items() if a in (1, 2, 3, 4)
                           for d in v if (d != (0, 0)) == bouge)
            pilotes = [k for k in ks if nb(k, True) >= 2 and nb(k, True) >= nb(k, False)]
            immobiles = [k for k in ks if nb(k, True) == 0]
            if pilotes and immobiles:
                parts = [({}, [k for k in ks if k not in immobiles]), ({}, immobiles)]
        if len(parts) > 1:
            for g, (_sp, membres) in enumerate(parts):
                for k in membres:
                    code[k] = c if g == 0 else 512 + c + 16 * g
    if not code:
        return etats, {}
    out = []
    for t, e in enumerate(etats):
        res = [(code.get(ids[t][i], o[0]), o[1], o[2], o[3]) for i, o in enumerate(e)]
        out.append(tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1])))))
    carte = {o: code[ids[-1][i]] for i, o in enumerate(etats[-1]) if ids[-1][i] in code}  # dernière image : objet → classe
    return out, carte


def heriter_classes(brut_dernier, carte, e):
    """Image nouvelle : chaque objet apparié (même couleur et forme) à un objet de la dernière image vue en prend la
    classe de comportement (`carte` : objet brut de la dernière image → classe)."""
    paires, _ = apparier(brut_dernier, e)
    res = list(e)
    for i, j in paires:
        if j is not None and brut_dernier[i] in carte:
            res[j] = (carte[brut_dernier[i]], e[j][1], e[j][2], e[j][3])
    return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))


def couleur_vraie(code):
    """Classe → couleur dessinée : un détail reclassé (code ≥ 16) garde sa couleur d'origine (code mod 16)."""
    return code % 16 if code >= 16 else code


def _accroches(e):
    """(couleur, forme, couleur hôte, forme hôte, dx, dy) de chaque objet touchant (4-voisins) un objet d'une autre couleur."""
    occ = {c: j for j, o in enumerate(e) for c in cellules(o)}
    out = {}
    for i, b in enumerate(e):
        cb = cellules(b)
        voisins = {(x + dx, y + dy) for x, y in cb for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - cb
        for j in {occ[c] for c in voisins if c in occ}:
            h = e[j]
            if h[0] != b[0] and h[0] < 16:
                out.setdefault(i, set()).add((b[0], b[1], h[0], h[1], b[2] - h[2], b[3] - h[3]))
    return out


def details(etats):
    """Accroches présentes sur CHAQUE image, dont l'objet a changé de position au moins une fois (hôte mobile)."""
    if len(etats) < 2:
        return frozenset()
    par_image = [_accroches(e) for e in etats]
    communes = set.intersection(*[set().union(*a.values()) if a else set() for a in par_image])
    garde = set()
    for k in communes:  # hôte mobile : l'ensemble des positions de ces objets change d'une image à l'autre
        pos = [frozenset((etats[t][i][2], etats[t][i][3]) for i, ks in a.items() if k in ks) for t, a in enumerate(par_image)]
        if len(set(pos)) > 1:
            garde.add(k)
    return frozenset(garde)


def reclasser(e, ds):
    """Donne aux détails `ds` leur classe propre (voir details) ; e trié comme objets()."""
    if not ds:
        return e
    acc = _accroches(e)
    res = []
    for i, o in enumerate(e):
        k = next((k for k in sorted(acc.get(i, ())) if k in ds), None)
        res.append((o[0] + 16 * (k[2] + 1), o[1], o[2], o[3]) if k else o)
    return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))


def completer_amodal(etats, cs, fond, exclues=frozenset(), futur=False, diagonales=frozenset()):
    """Occultation (CCM-079-C, banc diag_rejeu : 147 transitions sur 276 non rejouées sont du « décor » qui change de forme
    quand un mobile passe dessus) : les classes déjà vues bouger (passé seulement) gardent leurs objets ; ailleurs, chaque
    case couverte par un mobile reprend la dernière couleur de décor vue à cet endroit. → nouveaux états."""
    mobiles, mem, out = set(), {}, []
    if futur:  # cases occupées par les classes qui bougent un jour, à chaque image (pour la complétion par l'avenir)
        tous = set()
        for t in range(1, len(etats)):
            paires, _ = apparier(etats[t - 1], etats[t])
            tous |= {etats[t - 1][i][0] for i, j in paires
                     if j is not None and (etats[t][j][2], etats[t][j][3]) != (etats[t - 1][i][2], etats[t - 1][i][3])}
        occupes = [{(o[3] + dy, o[2] + dx) for o in e if o[0] in tous for dx, dy in o[1]} for e in etats]
    for t, (e, c) in enumerate(zip(etats, cs, strict=True)):
        if t > 0:
            paires, _ = apparier(etats[t - 1], e)
            mobiles |= {etats[t - 1][i][0] for i, j in paires
                        if j is not None and (e[j][2], e[j][3]) != (etats[t - 1][i][2], etats[t - 1][i][3])}
        bougent = tous if futur else mobiles  # par l'avenir, les classes qui bougent un jour sont connues dès la 1re image
        mob = [o for o in e if o[0] in bougent]  # (g50t N1 : le sol sous le joueur, découvert au 1er coup)
        sous = {(o[3] + dy, o[2] + dx) for o in mob for dx, dy in o[1]}
        decor = np.array(c, copy=True)
        for (y, x), v in mem.items():
            if (y, x) in sous:
                decor[y, x] = v
        if futur:  # apprentissage sur un historique complet : la case cachée prend la couleur qu'elle aura en
            for y, x in sous:  # réapparaissant (un interrupteur qui change de couleur SOUS le joueur, T4 y000 L2)
                v = next((int(cs[u][y, x]) for u in range(t + 1, len(cs)) if (y, x) not in occupes[u]), None)
                if v is not None:
                    decor[y, x] = v
        for y in range(decor.shape[0]):
            for x in range(decor.shape[1]):
                if (y, x) not in sous:
                    mem[(y, x)] = int(c[y, x])
        stat = [o for o in objets(decor, fond, exclues, diagonales) if o[0] not in bougent or (o[3], o[2]) not in sous]
        out.append(tuple(sorted(mob + [o for o in stat if o not in mob], key=lambda o: (o[0], o[2], o[3], sorted(o[1])))))
    return out


def apparier(e0, e1):
    """Appariement par classe (couleur, forme) à déplacement total minimal. Renvoie [(i0, i1|None)], [i1 nouveaux]."""
    paires, nouveaux = [], []
    par0, par1 = {}, {}
    for i, o in enumerate(e0):
        par0.setdefault((o[0], o[1]), []).append(i)
    for i, o in enumerate(e1):
        par1.setdefault((o[0], o[1]), []).append(i)
    for k, l0 in par0.items():
        l1 = par1.get(k, [])
        def cout(p, l0=l0, l1=l1):
            return sum(abs(e0[a][2] - e1[b][2]) + abs(e0[a][3] - e1[b][3]) for a, b in zip(l0, p, strict=False) if b is not None)
        if len(l0) <= 6 and len(l1) <= 6:
            pad = l1 + [None] * max(0, len(l0) - len(l1))
            best = min(permutations(pad, len(l0)), key=cout)
        else:  # glouton : chaque objet vers le plus proche encore libre
            libres, best = list(l1), []
            for a in l0:
                b = min(libres, key=lambda b, a=a: abs(e0[a][2] - e1[b][2]) + abs(e0[a][3] - e1[b][3])) if libres else None
                best.append(b)
                if b is not None:
                    libres.remove(b)
        paires += list(zip(l0, best, strict=True))
        nouveaux += [b for b in l1 if b not in best]
    for k, l1 in par1.items():
        if k not in par0:
            nouveaux += l1
    return paires, nouveaux


def desouder(etats):
    """D (CHRYS_DESOUDER ; re86 N5, CCM-157-C (a)) : un objet de l'image t qui CONTIENT au moins deux objets distincts de
    l'image t-1 (≥ 80 % de leurs cases, quelle que soit leur couleur d'avant : une pièce repeinte compte) est
    une soudure (8-connexité, contact) : il est recoupé en ces objets (forme d'avant, couleur d'aujourd'hui) ; les cases
    restantes (la pièce qui a bougé) forment un objet de plus. Images traitées dans l'ordre (t-1 déjà recoupée)."""
    out = [etats[0]] if etats else []
    for e in etats[1:]:
        prec, res = out[-1], []
        for o in e:
            cs = cellules(o)
            dedans = [p for p in prec if len(p[1]) > 1 and len(cellules(p) & cs) >= 0.8 * len(p[1])]
            if len(dedans) < 2:
                res.append(o)
                continue
            pris = set()
            for p in sorted(dedans, key=lambda p: -len(p[1])):
                c = (cellules(p) & cs) - pris
                if c:
                    pris |= c
                    x0, y0 = min(x for x, _ in c), min(y for _, y in c)
                    res.append((o[0], frozenset((x - x0, y - y0) for x, y in c), x0, y0))
            reste = cs - pris
            if reste:
                x0, y0 = min(x for x, _ in reste), min(y for _, y in reste)
                res.append((o[0], frozenset((x - x0, y - y0) for x, y in reste), x0, y0))
        out.append(tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1])))))
    return out


def creux(g, s):
    """D (CHRYS_CREUX ; ka59, CCM-055-E : cibles = cadres d'un pixel autour d'un creux 3×3) : composantes (8-connexité) qui
    entourent un TROU d'une autre couleur (≤ 400 pixels : des cibles, pas un mur d'enceinte), que l'échelle s > 1 écraserait.
    → liste de (couleur, boîte (x0, y0, x1, y1), pixels du trou)."""
    from scipy.ndimage import binary_fill_holes, find_objects, label
    g = np.asarray(g)
    vals, cnt = np.unique(g, return_counts=True)
    fond = vals[cnt.argmax()]
    out = []
    for c in vals:
        if c == fond:
            continue
        lab, _ = label(g == c, structure=np.ones((3, 3)))
        for k, sl in enumerate(find_objects(lab), start=1):
            m = lab[sl] == k
            trou = binary_fill_holes(m) & ~m
            if not trou.any() or m.sum() > 400:
                continue
            out.append((int(c), (sl[1].start, sl[0].start, sl[1].stop - 1, sl[0].stop - 1), int(trou.sum())))
    return out


def absorber_trous(etats, fond=None):
    """D (CHRYS_CREUX, CCM-258-C : à l'échelle 1, le trou d'une pièce de ka59 devient un objet qui bouge avec elle, et la
    sélection au clic n'est plus vue) : un objet ENTIÈREMENT enclos dans le trou d'un objet MOBILE (son identité se déplace
    au cours de la trajectoire) lui appartient (fusion), SEULEMENT s'il est de la couleur de l'hôte ou du fond (CCM-263-C :
    repeindre un trou d'une autre couleur casse le rejeu de la théorie ; un clic dans ce trou est rendu à l'hôte par la
    sélection au clic, côté C). Les cadres-cibles immobiles gardent leur creux, donc leur centre."""
    from scipy.ndimage import binary_fill_holes
    ids, _ = identites(etats)  # objet mobile = son identité change d'ancre au cours de la trajectoire (par objet, pas par
    pos = {}                    # couleur : à ka59, un cadre bouge et l'autre, de même forme, reste une cible)
    for e, ii in zip(etats, ids, strict=True):
        for o, k in zip(e, ii, strict=True):
            pos.setdefault(k, set()).add((o[2], o[3]))
    mobiles = {k for k, v in pos.items() if len(v) > 1}
    out = []
    for e, ii in zip(etats, ids, strict=True):
        e, pris, fusions = list(e), set(), {}
        for i, h in enumerate(e):
            if ii[i] not in mobiles or len(h[1]) < 8:
                continue
            cs = cellules(h)
            x0, y0 = min(x for x, _ in cs), min(y for _, y in cs)
            m = np.zeros((max(y for _, y in cs) - y0 + 1, max(x for x, _ in cs) - x0 + 1), bool)
            for x, y in cs:
                m[y - y0, x - x0] = True
            trou = {(x + x0, y + y0) for y, x in zip(*np.nonzero(binary_fill_holes(m) & ~m), strict=True)}
            if not trou:
                continue
            for j, o in enumerate(e):
                if j != i and j not in pris and o[0] in (h[0], fond) and cellules(o) <= trou:
                    pris.add(j)
                    fusions.setdefault(i, set()).update(cellules(o))
        res = []
        for i, o in enumerate(e):
            if i in pris:
                continue
            if i in fusions:
                cs = cellules(o) | fusions[i]
                x0, y0 = min(x for x, _ in cs), min(y for _, y in cs)
                o = (o[0], frozenset((x - x0, y - y0) for x, y in cs), x0, y0)
            res.append(o)
        out.append(tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1])))))
    return out


def lisser(g):
    """D (CHRYS_LISSAGE, bp35) : un pixel isolé dont les 4 voisins ont une même autre couleur prend cette couleur (texture
    de fond pointillée) ; avant l'échelle et les cases."""
    g = np.asarray(g)
    p = np.pad(g, 1, mode="edge")
    n = (p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:])
    m = (n[0] == n[1]) & (n[1] == n[2]) & (n[2] == n[3]) & (n[0] != g)
    out = g.copy()
    out[m] = n[0][m]
    return out


def _translation(a, b, r):
    """(dx, dy) tel que b[y][x] = a[y + dy][x + dx] sur le recouvrement (≥ tiers de l'image) le mieux, et son taux
    d'erreur ; (0, 0) si l'image immobile fait aussi bien."""
    h, w = a.shape
    best = (float((a != b).mean()), 0, 0)
    if best[0] < 0.15:  # moins de 15 % de l'écran change : des objets bougent, la caméra non (ar25 ≤ 4 %, bp35 ≥ 23 %)
        return 0, 0, best[0]
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if (dx, dy) == (0, 0) or (h - abs(dy)) * (w - abs(dx)) < h * w / 3:
                continue
            sa = a[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)]
            sb = b[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
            e = float((sa != sb).mean())
            if e < best[0] / 2:  # un défilement doit expliquer nettement mieux que l'immobilité
                best = (e, dx, dy)
    return best[1], best[2], best[0]


def defilement(cs, fond, r=None):
    """D (CHRYS_DEFILEMENT, bp35 : la caméra interne suit le joueur) : images en cases → (mondes, caméras). Position de
    la caméra cumulée d'une image à l'autre (meilleure translation) ; les rangées et colonnes d'écran qui ne suivent pas
    le défilement (HUD) sont mises au fond ; le monde est une MÉMOIRE (une case vue garde sa dernière couleur, une case
    jamais vue est du fond). Sans défilement : (cs, None)."""
    cs = [np.asarray(c) for c in cs]
    h, w = cs[0].shape
    r = r or 2 * max(h, w) // 3
    cam, pas = [(0, 0)], []
    for a, b in pairwise(cs):
        dx, dy, _ = _translation(a, b, r)
        pas.append((dx, dy))
        cam.append((cam[-1][0] + dx, cam[-1][1] + dy))
    if all(p == (0, 0) for p in pas):
        return cs, None
    lig, col = np.zeros(h), np.zeros(w)  # HUD : l'immobile explique mieux que le défilement
    for (a, b), (dx, dy) in zip(pairwise(cs), pas, strict=True):
        if (dx, dy) == (0, 0):
            continue
        im = a != b
        dec = im.copy()  # hors du recouvrement (cases tout juste découvertes) : aucune preuve ni pour ni contre le HUD
        dec[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)] = (
            a[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] != b[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)])
        lig += (im & ~dec).sum(1) - (dec & ~im).sum(1)
        col += (im & ~dec).sum(0) - (dec & ~im).sum(0)
    hud = np.zeros((h, w), bool)
    hud[lig < 0, :] = True
    hud[:, col < 0] = True
    x0, y0 = min(c[0] for c in cam), min(c[1] for c in cam)
    W, H = w + max(c[0] for c in cam) - x0, h + max(c[1] for c in cam) - y0
    mem, mondes = np.full((H, W), fond, dtype=cs[0].dtype), []
    for c, (cx, cy) in zip(cs, cam, strict=True):
        z = mem[cy - y0:cy - y0 + h, cx - x0:cx - x0 + w]
        z[~hud] = c[~hud]
        mondes.append(mem.copy())
    return mondes, [(cx - x0, cy - y0) for cx, cy in cam]


class Trajectoire:
    """Suite d'images d'une même vie et d'un même niveau, avec les actions jouées entre elles."""

    def __init__(self, grilles, actions, atomiques=None, sans_fond=False, ech=None, exclues_heritees=frozenset(),
                 formes_heritees=None):
        assert len(grilles) == len(actions) + 1
        self.grilles = grilles  # C (CW-333, CHRYS_JAUGE) : images brutes, pour lire la barre de budget (interface exclue)
        if os.environ.get("CHRYS_LISSAGE") == "1" and ech is None:  # D (bp35) : texture pointillée effacée, seulement
            lisses = [lisser(g) for g in grilles]                         # si c'est une TEXTURE (≥ 100 pixels isolés
            if (max(int((lisses[i] != np.asarray(grilles[i])).sum())      # par image : bp35 150, les autres ≤ 24) qui
                    for i in {0, len(grilles) // 2, len(grilles) - 1}) >= 100
                    and echelle(lisses[:1])[0] > echelle(grilles[:1])[0]):  # cachait une échelle plus grossière
                grilles = lisses
                if os.environ.get("CHRYS_DEFILEMENT") == "1":  # l'écran défile : échelle de la 1re image seule (stable)
                    ech = echelle(lisses[:1])
        # C : CHRYS_ECHELLE_1RE=1 → échelle de la 1re image du niveau seule : stable quand la trajectoire s'allonge (sinon
        # l'échelle dépend des images échantillonnées : re86 3 ou 4, ar25 3 ou 4, sp80 14, 17 ou 6 selon la longueur)
        self.s, self.ox, self.oy = ech or (echelle_par_objets(grilles) if os.environ.get("CHRYS_ECHELLE_OBJETS") == "1"
                                           else echelle(grilles[:1] if os.environ.get("CHRYS_ECHELLE_1RE") == "1" else grilles))
        self.creux = None
        if ech is None and self.s > 1 and os.environ.get("CHRYS_CREUX") == "1":
            # D (ka59, CCM-055-E) : des cibles CREUSES (cadre fin autour d'un trou) seraient écrasées à l'échelle s : on
            # perçoit au pixel, pour que « dans le creux » et « sur le cadre » restent distincts
            self.creux = creux(grilles[0], self.s)
            if self.creux:
                self.s, self.ox, self.oy = 1, 0, 0
        # D (CW-234) : l'interface persiste d'un niveau à l'autre ; masque des niveaux réussis (même géométrie) ajouté
        self.exclues = frozenset(masque_cases(grilles, self.s, self.ox, self.oy)) | frozenset(exclues_heritees)
        cs = self.cases = [cases(g, self.s, self.ox, self.oy) for g in grilles]
        self.fond = -1 if sans_fond else Counter(np.concatenate([c.ravel() for c in cs]).tolist()).most_common(1)[0][0]
        self.camera = None  # D (CHRYS_DEFILEMENT) : position de l'écran dans le monde, en cases, par image
        if os.environ.get("CHRYS_DEFILEMENT") == "1":
            mondes, cam = defilement(cs, self.fond)
            if cam is not None:
                cs, self.camera, self.exclues = mondes, cam, frozenset()  # le HUD est déjà au fond
                self.cases = cs
        self.taille = cs[0].shape[::-1]  # (largeur, hauteur) en cases
        self.diagonales = (couleurs_diagonales(cs[0], self.fond, self.exclues)  # C (re86 N2) : pièces en diagonale
                           if os.environ.get("CHRYS_DIAGONALES") == "1" else frozenset())
        self.etats = [objets(c, self.fond, self.exclues, self.diagonales) for c in cs]
        if self.creux:  # D (CCM-258-C) : le trou d'une pièce mobile appartient à la pièce
            self.etats = absorber_trous(self.etats, self.fond)
        if os.environ.get("CHRYS_AMODAL", "0") in ("1", "2"):  # C (CCM-079-C) : décor complété sous les mobiles ;
            self.etats = completer_amodal(self.etats, cs, self.fond, self.exclues,  # 2 = aussi par l'avenir (CCM-081-C)
                                          futur=os.environ.get("CHRYS_AMODAL") == "2", diagonales=self.diagonales)
        # D (CW-201/208) : détails de sprites multicolores = composantes collées à un hôte mobile au même décalage sur
        # TOUTES les images ; classe propre (code couleur + 16·(couleur de l'hôte + 1)), rendue dans sa vraie couleur
        # D (CW-215 (1)) : tuiles voisines de même couleur = objets distincts, découpés sur la grille de tuiles déduite des
        # rectangles qui changent à chaque coup (taille et pas communs)
        self.tuiles = (grille_tuiles(cs, self.exclues, actions) if os.environ.get("CHRYS_TUILES", "0") == "1" else None)
        self.etats = [decouper_tuiles(e, self.tuiles) for e in self.etats]
        self.marqueur = os.environ.get("CHRYS_MARQUEUR", "1") == "1"  # C (CCM-102-C) : objet coupé par un marqueur (défaut : allumé, CCM-130-C)
        if self.marqueur:  # sélection seulement : le marqueur se pose, sur la trajectoire, sur ≥ 2 hôtes de couleurs
            hotes = {}       # différentes (re86) ; sinon c'est un détail de sprite (point central du joueur de ls20)
            for e in self.etats:
                r = recoller_marqueurs(e, diagonales=self.diagonales)
                for mk in (o for o in r if o[0] >= MARQUEUR):
                    hotes.setdefault(mk[0] - MARQUEUR, set()).update(
                        o[0] for o in r if o[0] < MARQUEUR and (mk[2], mk[3]) in cellules(o))
            self.marqueurs = frozenset(k for k, h in hotes.items() if len(h) >= 2)
            if os.environ.get("CHRYS_PORTEUR_BOITE") == "1":  # C (re86 N5) : un marqueur de sélection est UNIQUE dans
                plus = {k for e in self.etats for k in self.marqueurs  # chaque image ; les centres des marques (9, plusieurs
                        if sum(1 for o in recoller_marqueurs(e, frozenset({k}), self.diagonales) if o[0] == MARQUEUR + k) > 1}
                self.marqueurs = self.marqueurs - plus  # par image) ne le sont pas
            self.marqueur = bool(self.marqueurs)
            self.etats = ([recoller_marqueurs(e, self.marqueurs, self.diagonales) for e in self.etats] if self.marqueur
                          else self.etats)
        if os.environ.get("CHRYS_DESOUDER") == "1":  # D (re86 N5) : objets soudés au contact recoupés selon l'image d'avant
            self.etats = desouder(self.etats)
        # D (CCM-080-C) : classe = (couleur, forme) quand une couleur a des formes qui bougent et d'autres jamais
        self.formes = formes_mobiles(self.etats) if os.environ.get("CHRYS_FORMES", "1") == "1" else {}
        if formes_heritees and os.environ.get("CHRYS_FORMES", "1") == "1":  # C (g50t N2, CCM-221-C) : table d'un niveau
            self.formes = {**formes_heritees, **self.formes}              # déjà vu : le joueur garde sa classe
        self.etats = [reclasser_formes(e, self.formes) for e in self.etats]
        self.details = details(self.etats) if os.environ.get("CHRYS_DETAILS", "0") == "1" else frozenset()
        self.etats = [reclasser(e, self.details) for e in self.etats]
        if atomiques is None:  # couleurs dont les composantes fusionnent/se séparent à nombre de cases constant, plus petite = 1 case
            atomiques = set()
            for col in {o[0] for e in self.etats for o in e}:
                formes = [sorted(len(o[1]) for o in e if o[0] == col) for e in self.etats]
                conserve = len({sum(f) for f in formes}) == 1  # même nombre de cases : fusion par mouvement, pas recoloriage
                if (conserve and len({tuple(f) for f in formes}) > 1 and min(min(f, default=9) for f in formes) == 1
                        and col not in self.diagonales):  # une pièce diagonale n'est pas un tas de cases (re86 N2)
                    atomiques.add(col)
        self.atomiques = frozenset(atomiques)
        self.etats = [self.decouper(e) for e in self.etats]
        self.actions = [self.action_cases(a, i) for i, a in enumerate(actions)]
        # D (CW-239) : objets de même couleur et même forme qui réagissent DIFFÉREMMENT à la même action (m0r0 : miroir ;
        # ka59 : un seul des deux bouge) → classes distinctes, sinon aucune loi de déplacement n'est induisible
        self._bruts, self._carte = list(self.etats), {}
        if os.environ.get("CHRYS_COMPORTEMENT", "1") == "1":
            self.etats, self._carte = comportements(self.etats, self.actions, self.atomiques)

    def decouper(self, e):
        res = [o for o in e if o[0] not in self.atomiques]
        res += [(o[0], frozenset({(0, 0)}), x, y) for o in e if o[0] in self.atomiques for x, y in cellules(o)]
        return tuple(sorted(res, key=lambda o: (o[0], o[2], o[3], sorted(o[1]))))

    def action_cases(self, a, i=None):
        """Action en cases : entier 1..5/7, ou ('clic', x, y) pour ACTION6 donnée en pixels (en cases du MONDE quand
        l'écran défile : position de la caméra avant le coup i)."""
        if isinstance(a, tuple):
            cx, cy = (0, 0) if self.camera is None else self.camera[-1 if i is None else i]
            return ("clic", (a[1] - self.ox) // self.s + cx, (a[2] - self.oy) // self.s + cy)
        return a

    def etat(self, g):
        e = decouper_tuiles(objets(cases(g, self.s, self.ox, self.oy), self.fond, self.exclues,
                                   getattr(self, "diagonales", frozenset())), self.tuiles)
        e = reclasser_formes(recoller_marqueurs(e, self.marqueurs, getattr(self, "diagonales", frozenset()))
                             if getattr(self, "marqueur", False) else e, self.formes)
        e = self.decouper(reclasser(e, self.details))
        if not self._carte:
            return e
        if e in self._bruts:  # image déjà vue : ses classes de comportement
            return self.etats[self._bruts.index(e)]
        return heriter_classes(self._bruts[-1], self._carte, e)  # image nouvelle : appariée à la dernière vue


def faits_asp(traj, debut=0, fin=None):
    """Faits CW-067.1 en texte ASP : obj/at/action par pas (vocabulaire de B, experiments/T2.8/vocabulaire.md)."""
    fin = len(traj.actions) if fin is None else fin
    lignes = []
    for t in range(debut, fin + 1):
        for i, o in enumerate(traj.etats[t]):
            lignes.append(f"obj(o{t}_{i},c{o[0]},f{abs(hash(o[1])) % 10**6}). at(o{t}_{i},{o[2]},{o[3]},{t}).")
        if t < fin:
            a = traj.actions[t]
            lignes.append(f"clic({a[1]},{a[2]},{t})." if isinstance(a, tuple) else f"action(a{a},{t}).")
    return "\n".join(lignes)


def modele_reduit(grilles, cases, exclure=None, palette=None, echelles=(1, 2, 3, 4), min_couleurs=2, max_rendus=10):
    """D (CCM-033-D, pour le but `copie` de C) : la cible dessinée EN MINIATURE (jeux « copier le modèle » : T4 famille
    tuiles, 23/104). `cases` : {(i, j): couleur} des tuiles du motif (i = rangée, j = colonne) ; `exclure` : (x0, y0, x1, y1)
    pixels de la zone des tuiles (la miniature est ailleurs) ; `palette` : couleurs que prennent les tuiles (défaut : celles
    de `cases`). Cherche une région STATIQUE (identique dans toutes les images) faite de n × m blocs s × s UNIFORMES dont
    les couleurs sont dans la palette (au moins `min_couleurs` couleurs distinctes). Rend une liste triée (plus grande
    échelle d'abord) de {"region": (x0, y0, x1, y1), "echelle": s, "origine": (ox, oy), "grille": ((c00, c01, …), …),
    "ecarts": cases dont la couleur actuelle diffère de la miniature}."""
    import numpy as np
    if not cases:
        return []
    gs = [np.asarray(g) for g in grilles]
    g0 = gs[0]
    statique = np.all([g == g0 for g in gs[1:]], axis=0) if len(gs) > 1 else np.ones(g0.shape, bool)
    n, m = max(i for i, _ in cases) + 1, max(j for _, j in cases) + 1
    pal = set(palette) if palette is not None else set(cases.values())
    H, W = g0.shape
    out = []
    for s in sorted(echelles, reverse=True):
        h, w = n * s, m * s
        for oy in range(H - h + 1):
            for ox in range(W - w + 1):
                if exclure is not None and not (ox + w <= exclure[0] or ox >= exclure[2] or oy + h <= exclure[1]
                                                or oy >= exclure[3]):
                    continue
                if any(r[0] <= ox and r[1] <= oy and ox + w <= r[2] and oy + h <= r[3] for r in (o["region"] for o in out)):
                    continue  # contenu dans une miniature déjà retenue (plus grande échelle) : un morceau d'elle
                z = g0[oy:oy + h, ox:ox + w]
                if not statique[oy:oy + h, ox:ox + w].all():
                    continue
                b = z.reshape(n, s, m, s)
                c = b[:, 0, :, 0]
                if not (b == c[:, None, :, None]).all() or not set(np.unique(c).tolist()) <= pal:
                    continue
                if len(np.unique(c)) < min_couleurs:
                    continue
                grille = tuple(tuple(int(v) for v in r) for r in c)
                ecarts = sum(cases.get((i, j)) != grille[i][j] for i in range(n) for j in range(m) if (i, j) in cases)
                out.append({"region": (ox, oy, ox + w, oy + h), "echelle": s, "origine": (ox, oy), "grille": grille,
                            "ecarts": ecarts})
                if len(out) >= max_rendus:
                    return out
    return out
