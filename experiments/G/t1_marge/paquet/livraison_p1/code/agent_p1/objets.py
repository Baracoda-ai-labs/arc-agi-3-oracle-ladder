"""Suivi de TOUS les objets de l'image que la théorie courante ne revendique pas.

La v4 ne compare que la pose du joueur et les bits de bascule : un objet qui bouge hors famille est invisible
pour son diagnostic. Ici, chaque composante (couleur, forme) non revendiquée est suivie image par image ;
sa théorie implicite v4 est « décor immobile ». Toute divergence devient une contradiction typée.
Aucune couleur ni coordonnée de niveau n'est codée : seules les composantes revendiquées par le modèle v4
(joueur, groupes porte/dalle/fil, HUD, jauge) sont exclues.
"""
from collections import Counter
import numpy as np

HAUT_JEU, BAS_JEU = 4, 62  # bande de jeu (HUD au-dessus, jauge en dessous), mêmes bornes que la v4


def composantes(mask):
    seen = set(); out = []
    H, W = mask.shape
    for y, x in zip(*np.where(mask)):
        p = (int(x), int(y))
        if p in seen:
            continue
        seen.add(p); pile = [p]; cs = {p}
        while pile:
            a, b = pile.pop()
            for z in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
                xx, yy = z
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and z not in seen:
                    seen.add(z); cs.add(z); pile.append(z)
        out.append(cs)
    return out


def forme(cs):
    x0 = min(x for x, y in cs); y0 = min(y for x, y in cs)
    return (x0, y0), frozenset((x - x0, y - y0) for x, y in cs)


def pixels_revendiques(model):
    """Pixels expliqués par la théorie v4 : composantes de couleur des groupes porte/dalle (fils inclus)."""
    rev = set()
    base = model.base
    for g in model.groups:
        for cs in composantes(base[:BAS_JEU] == g['color']):
            noeuds = set(g['doors']) | set(g['triggers'])
            if any((x + u, y + v) in cs for x, y in noeuds for u, v in model.shape):
                rev |= cs
    return rev


def objets_initiaux(model, image, min_px=4):
    """Objets non revendiqués, de taille >= min_px (les points isolés restent du décor/but v4)."""
    rev = pixels_revendiques(model)
    joueur = {(model.start[0] + u, model.start[1] + v) for u, v in model.shape}
    out = []
    zone = image[:BAS_JEU].copy(); zone[:HAUT_JEU] = 0
    for c in sorted(set(map(int, zone.flat)) - {0, model.floor}):
        for cs in composantes(zone == c):
            if len(cs) < min_px or cs & rev or cs <= joueur or cs & joueur:
                continue
            pos, f = forme(cs)
            out.append(dict(id=f"obj{len(out)}", couleur=c, forme=f, pos0=pos, taille=len(cs)))
    return out


def localiser(obj, image, pres=None, exclure=()):
    """Position de l'objet (même couleur, même forme) la plus proche de `pres`, ou None (absent/occulté).
    `exclure` : poses déjà attribuées par le modèle (fantômes enregistrés) — jamais confondues avec l'objet."""
    zone = image[:BAS_JEU].copy(); zone[:HAUT_JEU] = 0
    cands = []
    for cs in composantes(zone == obj['couleur']):
        pos, f = forme(cs)
        if f == obj['forme'] and pos not in exclure:
            d = abs(pos[0] - pres[0]) + abs(pos[1] - pres[1]) if pres else 0
            cands.append((d, pos))
    return min(cands)[1] if cands else None


def piste(obj, images, exclure=None):
    """Positions successives (None = invisible)."""
    out = []; pres = obj['pos0']
    for t, im in enumerate(images):
        p = localiser(obj, im, pres, exclure[t] if exclure and t < len(exclure) else ())
        out.append(p)
        if p is not None:
            pres = p
    return out


def portes_fermees(model, image):
    """Lecture de rendu : nœuds-portes dont l'empreinte porte >= 50 % de la couleur du groupe."""
    out = set()
    for g in model.groups:
        for d in g['doors']:
            n = sum(image[d[1] + v, d[0] + u] == g['color'] for u, v in model.shape)
            if n >= len(model.shape) * .5:
                out.add(tuple(d))
    return out


def transitions(model, images, actions, poses_joueur, exclure=None, objs=None):
    """Transitions enregistrées au niveau objet : une ligne par coup, pour chaque objet suivi.
    poses_joueur[t] = pose observée du joueur après le coup t (t=0 : image initiale)."""
    objs = objs if objs is not None else objets_initiaux(model, images[0])
    pistes = {o['id']: piste(o, images, exclure) for o in objs}
    lignes = []
    for t in range(1, len(images)):
        a = actions[t - 1]
        pj0, pj1 = poses_joueur[t - 1], poses_joueur[t]
        lignes.append(dict(t=t, action=a, joueur_avant=pj0, joueur_apres=pj1,
                           effectif=(a in (1, 2, 3, 4) and pj0 != pj1),
                           portes_fermees=sorted(portes_fermees(model, images[t])),
                           objets={o['id']: (pistes[o['id']][t - 1], pistes[o['id']][t]) for o in objs}))
    return objs, lignes


def contradictions_v4(objs, lignes):
    """Théorie implicite v4 : objet non revendiqué = décor immobile. Rend la liste des écarts typés."""
    out = []
    for L in lignes:
        for oid, (p0, p1) in L['objets'].items():
            if p0 == p1:
                continue
            if p0 is not None and p1 is not None:
                typ = 'deplacement'
            elif p1 is None:
                typ = 'disparition'
            else:
                typ = 'reapparition'
            out.append(dict(t=L['t'], objet=oid, type=typ, predit=p0, observe=p1, action=L['action'],
                            categorie='transition'))
    return out
