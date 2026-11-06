"""Navigation locale : silhouette retournable, grille, gravité et disparition au clic.
Modèle partiel et révisable, sans identité/couleur/position de jeu dans les règles.
"""

import math
from collections import Counter, deque

import numpy as np


class NavigationVisible:
    def __init__(self, images, actions):
        self.images = [np.asarray(g) for g in images]
        g = self.images[0]
        colors, counts = np.unique(g, return_counts=True)
        self.palette = {int(c) for c, n in zip(colors, counts) if 1 < n < 12}
        positions = [self.position(im) for im in self.images]
        pas = [
            abs(positions[i + 1][0] - positions[i][0])
            for i, a in enumerate(actions)
            if a in (3, 4) and positions[i + 1][0] != positions[i][0]
        ]
        self.pas = math.gcd(*pas) if pas else 0
        if self.pas < 2:
            raise ValueError("Pas de déplacement non identifié")
        self.free = Counter()
        s = self.pas
        for i, a in enumerate(actions):
            if positions[i] == positions[i + 1]:
                continue
            x, y = positions[i]
            patch = self.images[i + 1][y - s // 2 : y + s // 2, x - s // 2 : x + s // 2]
            self.free.update(int(c) for c in patch.ravel() if c not in self.palette)
        self.sol = self.free.most_common(1)[0][0]
        self.cassables = set()

    def position(self, g):
        if getattr(self, "perception_connexe", False):
            from perception_navigation import position

            return position(self, g)
        ys, xs = np.nonzero(np.isin(g, list(self.palette)))
        if not len(xs):
            raise ValueError("Silhouette absente")
        if max(xs) - min(xs) > 8 or max(ys) - min(ys) > 8:
            raise ValueError("Silhouette ambiguë")
        return math.ceil((int(min(xs)) + int(max(xs))) / 2), math.ceil((int(min(ys)) + int(max(ys))) / 2)

    def apprendre_clics(self, images, actions):
        preuves = []
        s = self.pas
        for k, a in enumerate(actions):
            if not isinstance(a, list):
                continue
            _, x, y = a
            avant, apres = np.asarray(images[k]), np.asarray(images[k + 1])
            # Une disparition locale sans défilement est identifiable sur ce couple.
            diff = avant != apres
            diff[-1] = False
            ys, xs = np.nonzero(diff)
            if not len(xs) or len(xs) > s * s * 2 or max(xs) - min(xs) > s or max(ys) - min(ys) > s:
                continue
            if not (min(xs) - s <= x <= max(xs) + s and min(ys) - s <= y <= max(ys) + s):
                continue
            if np.mean(apres[ys, xs] == self.sol) < 0.7:
                continue
            c = Counter(avant[ys, xs].tolist()).most_common(1)[0][0]
            if c not in self.palette and c != self.sol:
                self.cassables.add(c)
                preuves.append({"coup": k + 1, "surface": c, "pixels": len(xs)})
        return preuves

    def lire(self, g):
        s = self.pas
        x, y = self.position(g)
        ox = (x % s - s // 2) % s
        oy = (y % s - s // 2) % s
        n = (64 - ox) // s
        m = (63 - oy) // s
        grille = np.zeros((m, n), int)
        for j in range(m):
            for i in range(n):
                patch = g[oy + j * s : oy + (j + 1) * s, ox + i * s : ox + (i + 1) * s]
                grille[j, i] = Counter(patch.ravel().tolist()).most_common(1)[0][0]
        joueur = ((x - ox) // s, (y - oy) // s)
        grille[joueur[1], joueur[0]] = self.sol
        return grille, joueur, (ox, oy)

    def proposer(self, g, gravite=None, buts_connus=None):
        grid, start, origine = self.lire(g)
        h, w = grid.shape
        libres = {tuple(reversed(p)) for p in np.argwhere(grid == self.sol)}
        cass = {tuple(reversed(p)) for p in np.argwhere(np.isin(grid, list(self.cassables)))}
        # Le repos contre un plafond/sol départage les deux signes de gravité.
        x, y = start
        haut = (x, y - 1) in libres
        bas = (x, y + 1) in libres
        if gravite is None:
            if haut == bas:
                raise ValueError("Sens de gravité ambigu dans cette vue")
            gravite = -1 if not haut else 1
        if gravite not in (-1, 0, 1):
            raise ValueError("Gravité hors catalogue")
        # Nouvelles petites composantes de couleur : buts candidats, jamais vérité.
        connus = set(self.palette) | self.cassables | {self.sol}
        terrain = Counter(grid.ravel().tolist())
        connus.update(c for c, n in terrain.items() if n > 2)
        buts = set()
        for j in range(h):
            for i in range(w):
                patch = g[
                    origine[1] + j * self.pas : origine[1] + (j + 1) * self.pas,
                    origine[0] + i * self.pas : origine[0] + (i + 1) * self.pas,
                ]
                if (buts_connus is not None and any(c in buts_connus for c in np.unique(patch))) or (
                    buts_connus is None
                    and any(2 <= int((g == c).sum()) <= self.pas * self.pas for c in np.unique(patch) if c not in connus)
                ):
                    buts.add((i, j))

        def settle(p, removed):
            while gravite and (p[0], p[1] + gravite) in libres | set(removed) | buts:
                p = (p[0], p[1] + gravite)
            return p

        q = deque([(start, frozenset(), [])])
        seen = {(start, frozenset())}
        best = None
        nodes = 0
        while q and nodes < 12000:
            pos, removed, path = q.popleft()
            nodes += 1
            score = (pos in buts, gravite * pos[1], -len(path))
            if path and (best is None or score > best[0]):
                best = (score, path, pos)
            if pos in buts and path:
                break
            if len(path) >= 10:
                continue
            choices = []
            for code, dx in [(3, -1), (4, 1)]:
                p = (pos[0] + dx, pos[1])
                if p in libres | set(removed) | buts:
                    choices.append((code, settle(p, removed), removed))
            for cell in sorted(cass - set(removed)):
                rem = removed | {cell}
                choices.append(
                    (
                        [
                            "clic",
                            origine[0] + cell[0] * self.pas + self.pas // 2,
                            origine[1] + cell[1] * self.pas + self.pas // 2,
                        ],
                        settle(pos, rem),
                        rem,
                    )
                )
            for action, p, rem in choices:
                key = (p, rem)
                if key not in seen:
                    seen.add(key)
                    q.append((p, rem, path + [action]))
        if best is None:
            raise ValueError("Aucun chemin local")
        first = best[1][0]
        removed = frozenset()
        if isinstance(first, list):
            removed = frozenset({((first[1] - origine[0]) // self.pas, (first[2] - origine[1]) // self.pas)})
            next_pos = settle(start, removed)
        else:
            next_pos = settle((start[0] + (-1 if first == 3 else 1), start[1]), removed)
        return {
            "position_suivante_locale": next_pos,
            "action": best[1][0],
            "plan_local": best[1],
            "position": start,
            "destination": best[2],
            "gravite_hypothese": gravite,
            "buts_hypothetiques": sorted(buts),
            "noeuds": nodes,
            "pas": self.pas,
            "origine": origine,
            "modele_partiel": True,
        }
