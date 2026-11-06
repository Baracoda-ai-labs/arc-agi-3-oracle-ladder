"""Perception par abstractions concurrentes (aucune couleur, aucun nom de jeu).

A1 : composantes connexes par couleur (4-voisinage) ; type = (couleur, forme).
A2 : groupes multicolores (8-voisinage, tout pixel non fond) ; type = (palette, forme).
A3 : tuiles d'une grille régulière (pas et décalage appris du déplacement du contrôlé) ; type = contenu de la tuile
     (motifs répétés : deux tuiles identiques ont le même type).
Le choix entre abstractions n'est pas imposé : la table des interactions note les effets sous chacune, et celle dont
les effets sont cohérents sert à prédire.
"""
import hashlib
import numpy as np
from scipy import ndimage

S4 = ndimage.generate_binary_structure(2, 1)
S8 = ndimage.generate_binary_structure(2, 2)


def fond(im):
    v, c = np.unique(im, return_counts=True)
    return int(v[np.argmax(c)])


def h(b):
    return hashlib.sha1(np.ascontiguousarray(b).tobytes()).hexdigest()[:10]


def objets(im, max_obj=400):
    """Liste d'objets sous A1 et A2 : dict(abs, type, c, n, x, y (pixel représentatif), bbox, bord)."""
    bg = fond(im); out = []
    for col in np.unique(im):
        if col == bg:
            continue
        lab, n = ndimage.label(im == col, S4)
        if n == 0:
            continue
        sl = ndimage.find_objects(lab)
        for i, s in enumerate(sl, 1):
            m = lab[s] == i
            out.append(_obj('A1', ('c', int(col), h(m), m.shape), im, s, m, int(col)))
            if len(out) > max_obj:
                return out
    lab, n = ndimage.label(im != bg, S8)
    for i, s in enumerate(ndimage.find_objects(lab), 1):
        m = lab[s] == i
        cols = tuple(sorted(set(int(v) for v in np.unique(im[s][m]))))
        if len(cols) < 2:
            continue                      # déjà vu sous A1
        out.append(_obj('A2', ('g', cols, h(np.where(m, im[s].astype(np.int16), -1)), m.shape), im, s, m, cols[0]))
    return out


def _obj(ab, typ, im, s, m, col):
    ys, xs = np.nonzero(m)
    my, mx = ys.mean(), xs.mean()
    k = int(np.argmin((xs - mx) ** 2 + (ys - my) ** 2))
    y0, x0 = s[0].start, s[1].start
    return dict(abs=ab, type=typ, c=col, n=int(m.sum()), x=int(x0 + xs[k]), y=int(y0 + ys[k]),
                bbox=(x0, y0, s[1].stop - 1, s[0].stop - 1),
                bord=bool(x0 == 0 or y0 == 0 or s[1].stop == 64 or s[0].stop == 64))


def types_au_pixel(im, x, y, objs):
    """Types (A1 et A2) des objets qui contiennent le pixel (x, y)."""
    out = []
    for o in objs:
        x0, y0, x1, y1 = o['bbox']
        if x0 <= x <= x1 and y0 <= y <= y1:
            if o['abs'] == 'A1' and im[y, x] == o['c']:
                out.append(o['type'])
            elif o['abs'] == 'A2' and im[y, x] != fond(im):
                out.append(o['type'])
    return out


def translation(before, after, axe):
    """Déplacement rigide dominant parmi les pixels changés, le long d'un axe ('x' ou 'y').
    Rend (s, masque_arrivee) ou (0, None). s signé, |s| ≤ 16."""
    ch = before != after
    n = int(ch.sum())
    if n == 0:
        return 0, None
    best = (0, 0, None)
    for s in list(range(1, 17)) + list(range(-16, 0)):
        if axe == 'x':
            prev = np.roll(before, s, axis=1); valid = np.zeros_like(ch)
            if s > 0:
                valid[:, s:] = True
            else:
                valid[:, :s] = True
        else:
            prev = np.roll(before, s, axis=0); valid = np.zeros_like(ch)
            if s > 0:
                valid[s:, :] = True
            else:
                valid[:s, :] = True
        arr = ch & valid & (after == prev)
        sc = int(arr.sum())
        if sc > best[0]:
            best = (sc, s, arr)
    sc, s, arr = best
    if sc >= max(2, 0.3 * n / 2):
        return s, arr
    return 0, None
