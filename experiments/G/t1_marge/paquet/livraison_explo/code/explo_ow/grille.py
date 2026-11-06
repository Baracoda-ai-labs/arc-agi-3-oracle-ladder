"""Monde en grille appris : contrôlé (gabarit de pixels), pas et décalage de la grille, déplacement par touche,
types de tuiles (motifs répétés), navigation et poussée planifiées sur le modèle appris.

Rien n'est codé par jeu : le pas vient du premier déplacement rigide observé, les murs/sols/pièces poussables viennent
du tableau des interactions (effet observé quand le contrôlé essaie d'entrer dans une tuile d'un type donné).
"""
import heapq
from collections import deque
import numpy as np
from .perception import translation, h

DIR = (1, 2, 3, 4)


class Grille:
    def __init__(self):
        self.delta = {}            # touche -> (dx, dy) en pixels
        self.gab = None            # (dy, dx, couleurs) pixels du contrôlé relatifs à sa position
        self.pos = None            # position (x, y) en pixels du coin du gabarit
        self.sx = self.sy = None; self.ox = self.oy = 0
        self.masque_lignes = set(); self.issues = {}

    # ------------------------------------------------------------ apprentissage
    def pret(self):
        return self.gab is not None and self.sx and self.sy and self.pos is not None

    def observer_touche(self, a, im0, im1):
        """Après une touche directionnelle : apprend le déplacement et le gabarit ; rend la nouvelle position."""
        if a not in DIR:
            return
        if self.pret() and a in self.delta:
            self.pos = self.localiser(im1, self.pos, self.delta[a], im0)
            return
        if self.gab is not None and self.pos is not None and a not in self.delta:
            # touche nouvelle : on suit le gabarit déjà connu plutôt que de deviner une translation globale
            p = self.localiser(im1, self.pos, (0, 0), im0)
            if p is not None and p != self.pos:
                d = (p[0] - self.pos[0], p[1] - self.pos[1])
                if (d[0] == 0) != (d[1] == 0) and max(abs(d[0]), abs(d[1])) >= 2:
                    self.delta[a] = d
                    self.delta.setdefault({1: 2, 2: 1, 3: 4, 4: 3}[a], (-d[0], -d[1]))
                    if d[0]:
                        self.sx = abs(d[0]); self.sy = self.sy or abs(d[0])
                    else:
                        self.sy = abs(d[1]); self.sx = self.sx or abs(d[1])
                    self.pos = p; self.ox = p[0] % self.sx; self.oy = p[1] % self.sy
                    return
            if p is not None and p == self.pos:
                return
        meilleur = None
        for axe in ('x', 'y'):
            s, arr = translation(im0, im1, axe)
            if s and arr is not None and abs(s) >= 2:
                if meilleur is None or arr.sum() > meilleur[2].sum():
                    meilleur = (axe, s, arr)
        if meilleur is None:
            if self.gab is not None and self.pos is not None:
                self.pos = self.localiser(im1, self.pos, (0, 0), im0)
            return
        axe, s, arr = meilleur
        d = (s, 0) if axe == 'x' else (0, s)
        self.delta[a] = d
        opp = {1: 2, 2: 1, 3: 4, 4: 3}[a]
        self.delta.setdefault(opp, (-d[0], -d[1]))
        if axe == 'x':
            self.sx = abs(s); self.sy = self.sy or abs(s)
        else:
            self.sy = abs(s); self.sx = self.sx or abs(s)
        if self.gab is None:
            ch = im0 != im1
            ys, xs = np.nonzero(ch)
            if len(xs) == 0:
                return
            x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
            # boîte d'arrivée = boîte des changements privée de la bande quittée
            if axe == 'x':
                bx0, bx1, by0, by1 = (x0 + s, x1, y0, y1) if s > 0 else (x0, x1 + s, y0, y1)
            else:
                bx0, bx1, by0, by1 = (x0, x1, y0 + s, y1) if s > 0 else (x0, x1, y0, y1 + s)
            if bx1 < bx0 or by1 < by0 or (bx1 - bx0 + 1) * (by1 - by0 + 1) > 400:
                return
            blk1 = im1[by0:by1 + 1, bx0:bx1 + 1]; blk0 = im0[by0:by1 + 1, bx0:bx1 + 1]
            m = blk1 != blk0
            if m.sum() < 2:
                m = np.ones_like(m)
            yy, xx = np.nonzero(m)
            self.gab = (yy, xx, blk1[yy, xx].copy())
            self.pos = (int(bx0), int(by0))
        else:
            p = self.localiser(im1, self.pos, d, im0)
            if p is None:                      # gabarit perdu (nouveau niveau, sprite changé) : on le réapprend
                self.gab = None; self.pos = None
                return self.observer_touche(a, im0, im1)
            self.pos = p
        if self.pos is not None and self.sx:
            self.ox = self.pos[0] % self.sx; self.oy = self.pos[1] % self.sy

    def localiser(self, im, pres, d=(0, 0), im_prev=None):
        """Position du gabarit la plus proche de pres+d (correspondance ≥ 85 %), ou None.
        Avec l'image précédente : si rien n'a changé, le contrôlé n'a pas bougé ; sinon sa nouvelle position doit
        recouvrir des pixels changés (évite les sosies immobiles : traînée, décor de même couleur)."""
        if self.gab is None:
            return None
        ch = None
        if im_prev is not None and pres is not None:
            ch = im != im_prev
            if not ch.any():
                return pres
        yy, xx, cc = self.gab
        H = 64 - (yy.max() + 1); W = 64 - (xx.max() + 1)
        if H < 0 or W < 0:
            return None
        sx, sy = self.sx or 1, self.sy or 1
        oxs = np.arange(pres[0] % sx, W + 1, sx) if pres else np.arange(0, W + 1)
        oys = np.arange(pres[1] % sy, H + 1, sy) if pres else np.arange(0, H + 1)
        best = None
        for _ in range(2):
            if len(oxs) and len(oys):
                X, Y = np.meshgrid(oxs, oys)
                X = X.ravel(); Y = Y.ravel()
                vals = im[Y[:, None] + yy[None, :], X[:, None] + xx[None, :]]
                sc = (vals == cc[None, :]).mean(axis=1)
                if ch is not None:
                    touche = ch[Y[:, None] + yy[None, :], X[:, None] + xx[None, :]].any(axis=1)
                    sc = np.where(touche | ((X == pres[0]) & (Y == pres[1])), sc, 0)
                ok = np.nonzero(sc >= 0.85)[0]
                if len(ok) and pres is None:
                    k = ok[np.argmax(sc[ok])]
                    best = (int(X[k]), int(Y[k]))
                    break
                if len(ok):
                    px, py = pres[0] + d[0], pres[1] + d[1]
                    k = ok[np.argmin(np.abs(X[ok] - px) + np.abs(Y[ok] - py) - sc[ok])]
                    best = (int(X[k]), int(Y[k]))
                    break
            oxs = np.arange(0, W + 1); oys = np.arange(0, H + 1)   # hors grille : recherche complète
        return best

    # ------------------------------------------------------------ tuiles
    def cellule(self, pos=None):
        p = pos or self.pos
        return ((p[0] - self.ox) // self.sx, (p[1] - self.oy) // self.sy)

    def dims(self):
        return (64 - self.ox) // self.sx, (64 - self.oy) // self.sy

    def tuiles(self, im, masque):
        """Types des tuiles : dict cellule -> hash du bloc (lignes de jauge masquées)."""
        W, H = self.dims(); out = {}
        for j in range(H):
            y = self.oy + j * self.sy
            if any(yy in masque for yy in range(y, y + self.sy)):
                continue
            for i in range(W):
                x = self.ox + i * self.sx
                out[(i, j)] = h(im[y:y + self.sy, x:x + self.sx])
        return out

    def dcell(self, a):
        d = self.delta.get(a)
        if not d:
            return None
        return (int(np.sign(d[0])), int(np.sign(d[1])))


def bfs_cases(depart, passable):
    """Distances et prédécesseurs (cellule, touche) sur les cellules franchissables."""
    dist = {depart: 0}; pred = {}; q = deque([depart])
    while q:
        c = q.popleft()
        for a, (dx, dy) in passable['dirs'].items():
            n = (c[0] + dx, c[1] + dy)
            if n in dist or not passable['ok'](n):
                continue
            dist[n] = dist[c] + 1; pred[n] = (c, a); q.append(n)
    return dist, pred


def chemin(pred, depart, cible):
    out = []; c = cible
    while c != depart:
        p, a = pred[c]; out.append(a); c = p
    return out[::-1]


def sokoban(acteur, boites, cibles, libre, dirs, max_noeuds=6000):
    """Meilleur d'abord sur (acteur, boîtes) : couvrir le plus de cibles possible. libre(c) : cellule franchissable
    hors boîtes. Rend (plan, couvertes) du meilleur état trouvé si couvertes > couvertes au départ, sinon None."""
    cibles = frozenset(cibles); b0 = frozenset(boites)
    def hscore(bs):
        rest = [c for c in cibles if c not in bs]; libres = [b for b in bs if b not in cibles]
        if not rest or not libres:
            return 0
        return sum(min(abs(b[0] - c[0]) + abs(b[1] - c[1]) for c in rest) for b in libres)
    cov0 = len(cibles & b0); objectif = min(len(cibles), len(b0))
    if objectif == 0 or cov0 >= objectif:
        return None
    dep = (acteur, b0); vus = {dep: None}; tas = [(hscore(b0), 0, 0, dep)]; n = 0; best = None; cpt = 0
    while tas and n < max_noeuds:
        _, g, _, s = heapq.heappop(tas); n += 1
        a_, bs = s; cov = len(cibles & bs)
        if cov > cov0 and (best is None or cov > best[1] or (cov == best[1] and g < best[2])):
            best = (s, cov, g)
            if cov >= objectif:
                break
        for a, (dx, dy) in dirs.items():
            nx = (a_[0] + dx, a_[1] + dy)
            if nx in bs:
                nb = (nx[0] + dx, nx[1] + dy)
                if nb in bs or not libre(nb):
                    continue
                s2 = (nx, (bs - {nx}) | {nb})
            else:
                if not libre(nx):
                    continue
                s2 = (nx, bs)
            if s2 in vus:
                continue
            vus[s2] = (s, a); cpt += 1
            heapq.heappush(tas, (g + 1 + 3 * hscore(s2[1]) - 6 * len(cibles & s2[1]), g + 1, cpt, s2))
    if best is None:
        return None
    plan = []; s = best[0]
    while vus[s] is not None:
        p, a = vus[s]; plan.append(a); s = p
    return plan[::-1], best[1]
