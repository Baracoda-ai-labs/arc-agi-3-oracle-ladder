# SPDX-License-Identifier: MIT-0
"""CW-040 (2a) : masque de hachage APPRIS par partie, à la place de la bordure fixe de 4 cases (graphe.etat).
But : retirer du hachage les compteurs (barres de pas, d'énergie) qui rendent chaque état unique, sans masquer l'état réel.
Zones = composantes 8-connexes des cases qui ont déjà changé lors d'un coup (même niveau, ni mort ni RESET).
Une zone est masquée si, sur au moins `min_coups` coups observés :
  - elle change à au moins `freq` des coups qui changent quelque chose (un compteur avance à chaque pas effectif) ;
  - au sein d'une même vie (entre deux RESET / morts / niveaux, cf. nouvelle_vie), son contenu ne revient presque jamais
    à une valeur déjà vue (part de contenus neufs ≥ `nouveaute`) : un compteur progresse, un joueur revient sur ses pas.
Une zone masquée fine (≤ 3 rangées ou colonnes, longue d'au moins 4) est une barre : on la prolonge sur toute la largeur
(ou hauteur) de la grille, car une barre qui se vide touche à chaque pas une case encore jamais changée.
Appris en ligne, seulement avec le passé. `etat_masque(g, niveau, cellules)` remplace graphe.etat (A le branche s'il veut)."""
import hashlib
import json
from itertools import pairwise


class Masque:
    def __init__(self, min_coups=8, freq=0.3, nouveaute=0.8, barres_seules=True, court=False):
        self.min_coups, self.freq, self.nouveaute, self.barres_seules = min_coups, freq, nouveaute, barres_seules
        self.court = court  # D (CW-215) : barre reconnue aussi sous min_coups si elle s'use de façon monotone
        self.coups = []  # (cases changées, grille après, vie)
        self.vie, self._cache = 0, None

    def nouvelle_vie(self):
        self.vie += 1

    def observer(self, g0, g1):
        ch = frozenset((r, c) for r, (a, b) in enumerate(zip(g0, g1, strict=True))
                       for c, (x, y) in enumerate(zip(a, b, strict=True)) if x != y)
        if ch:
            self.coups.append((ch, g1, self.vie))
        self._cache = None

    def zones(self):
        tout = set().union(*(ch for ch, _, _ in self.coups)) if self.coups else set()
        vu, zs = set(), []
        for p in sorted(tout):
            if p in vu:
                continue
            pile, z = [p], set()
            vu.add(p)
            while pile:
                r, c = pile.pop()
                z.add((r, c))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        q = (r + dr, c + dc)
                        if q in tout and q not in vu:
                            vu.add(q)
                            pile.append(q)
            zs.append(frozenset(z))
        return zs

    def cellules(self):
        if self._cache is not None:
            return self._cache
        n, m = len(self.coups), set()
        if n >= self.min_coups:
            for z in self.zones():
                touches = [(g, v) for ch, g, v in self.coups if ch & z]
                if len(touches) < self.freq * n or (self.barres_seules and not self._fine(z)):
                    continue
                cases = sorted(z)
                contenus = {(v, tuple(g[r][c] for r, c in cases)) for g, v in touches}
                if len(contenus) >= self.nouveaute * len(touches):
                    m |= self._barre(z, touches[-1][0])
        elif self.court and n >= 3:
            for z in self.zones():
                if self._fine(z) and self._monotone(z):
                    m |= self._barre(z, self.coups[-1][1])
        self._cache = frozenset(m)
        return self._cache

    def _monotone(self, z):
        """Jauge de niveau court : ≥ 3 coups (et ≥ 60 % des coups) la touchent ; chaque coup change des cases de z jamais
        changées avant (usure, pas un passage : un mobile qui longe le bord rechange la case qu'il quitte) ; et le centre
        des cases changées avance dans un seul sens le long de la ligne."""
        rs = {r for r, _ in z}
        axe = 1 if len(rs) <= 3 else 0  # ligne horizontale : on suit la colonne
        vus, centres = set(), []
        for ch, _, _ in self.coups:
            s = ch & z
            if not s:
                continue
            if s & vus:
                return False
            vus |= s
            centres.append(sum(p[axe] for p in s) / len(s))
        if len(centres) < max(3, 0.6 * len(self.coups)):
            return False
        d = [b - a for a, b in pairwise(centres)]
        return all(x > 0 for x in d) or all(x < 0 for x in d)

    @staticmethod
    def _fine(z):
        rs, cs = {r for r, _ in z}, {c for _, c in z}
        return (len(rs) <= 3 and len(cs) >= 4) or (len(cs) <= 3 and len(rs) >= 4)

    @staticmethod
    def _barre(z, g):
        rs, cs = {r for r, _ in z}, {c for _, c in z}
        if len(rs) <= 3 and len(cs) >= 4:
            return z | {(r, c) for r in rs for c in range(len(g[0]))}
        if len(cs) <= 3 and len(rs) >= 4:
            return z | {(r, c) for c in cs for r in range(len(g))}
        return z


def etat_masque(g, niveau, cellules):
    gg = [list(r) for r in g]
    for r, c in cellules:
        gg[r][c] = -1
    return hashlib.sha1(json.dumps([niveau, gg]).encode()).hexdigest()[:16]
