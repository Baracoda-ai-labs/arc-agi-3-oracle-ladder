# SPDX-License-Identifier: MIT-0
"""Voie 2 b (CW-028, CW-030 piste 1) : graphe des transitions observées, SANS LLM, calculé sur CPU.

Un nœud = état haché (intérieur de la grille, bordure de `bord` cases masquée : barres et compteurs ; + niveau).
Une arête = (état, coup) -> état suivant ; on marque les coups sans effet et mortels. Antériorité : Rudakov
« Explore It Till You Solve It » (2512.24156 : hachage, graphe, plus court chemin vers un état aux coups non testés),
BDR-Pro (rejeu du préfixe après une mort). Notre usage : le routeur rejoue ces chemins sans appeler le modèle, et le
modèle peut les interroger comme outils (frontier_path, replay_to, is_known_dead).
Coup = clé texte stable : "1".."5", "7", ou "6@r,c" (clic). Candidats d'un état = coups simples disponibles + un clic
au centre de chaque objet (composante connexe hors fond), petits objets d'abord (Blind Squirrel : un objet = un bouton)."""
import hashlib
import json
from collections import deque

from chrysalide.arc3.duck import segmentation


def cle(a, row=None, col=None):
    return f"6@{row},{col}" if int(a) == 6 else str(int(a))


def decle(k):
    if k.startswith("6@"):
        r, c = k[2:].split(",")
        return 6, int(r), int(c)
    return int(k), None, None


def etat(g, niveau=0, bord=4):
    h, w = len(g), len(g[0])
    dedans = [r[bord:w - bord] for r in g[bord:h - bord]]
    return hashlib.sha1(json.dumps([niveau, dedans]).encode()).hexdigest()[:16]


def candidats(g, actions_dispo, max_clics=24):
    simples = [cle(a) for a in actions_dispo if int(a) not in (0, 6)]
    clics = []
    if 6 in [int(a) for a in actions_dispo]:
        objets = sorted(segmentation(g), key=lambda o: o["size"])[:max_clics]
        for o in objets:
            r0, c0, r1, c1 = o["bbox"]
            clics.append(cle(6, (r0 + r1) // 2, (c0 + c1) // 2))
    return simples + clics


class Graphe:
    def __init__(self):
        self.aretes, self.cands, self.morts = {}, {}, set()

    def voir(self, s, cands):
        self.cands.setdefault(s, list(cands))

    def noter(self, s0, k, s1, mort=False):
        self.aretes.setdefault(s0, {})[k] = s1
        if mort:
            self.morts.add((s0, k))

    def non_testes(self, s):
        fait = self.aretes.get(s, {})
        return [k for k in self.cands.get(s, []) if k not in fait]

    def is_known_dead(self, s, k):
        return (s, k) in self.morts

    def _bfs(self, depart, but):
        """Plus court chemin (liste de coups) par arêtes connues, non mortelles et à effet, vers un état vérifiant but()."""
        prec, file = {depart: None}, deque([depart])
        while file:
            s = file.popleft()
            if s != depart and but(s):
                chemin = []
                while prec[s] is not None:
                    s, k = prec[s]
                    chemin.append(k)
                return chemin[::-1]
            for k, t in self.aretes.get(s, {}).items():
                if t not in prec and t != s and (s, k) not in self.morts:
                    prec[t] = (s, k)
                    file.append(t)
        return None

    def frontier_path(self, s):
        """Chemin vers l'état connu le plus proche qui a encore des coups non testés ([] si s en a lui-même)."""
        return [] if self.non_testes(s) else self._bfs(s, lambda t: bool(self.non_testes(t)))

    def replay_to(self, s, cible):
        return [] if s == cible else self._bfs(s, lambda t: t == cible)

    def prevision(self, s, k):
        """État suivant attendu si (s, k) a déjà été joué, sinon None (sert à la vérification pas à pas)."""
        return self.aretes.get(s, {}).get(k)

    def taille(self):
        return {"etats": len(self.cands), "aretes": sum(len(v) for v in self.aretes.values()), "morts": len(self.morts)}
