# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — perception ORACLE (objets_moteur de A, CCM-064-A) comme 3ᵉ découpage, POUR LES BANCS SEULEMENT :
isole la question « le moteur logique comprend-il un vrai jeu quand les objets sont justes ? ». Jamais dans un agent soumis.
Objet = (classe, forme, x, y) en cases de la vue caméra ; classe = entier pour (nom du sprite, couleurs du sprite).
Le juge est l'égalité exacte des ensembles d'objets (rejeu exact au niveau objets, CW-067)."""
import numpy as np
from arcengine.enums import GameAction, GameState

from chrysalide.arc3.logique.jeux import en_pixels, environnement, jouer_action
from chrysalide.arc3.logique.theorie import cle_objet
from chrysalide.arc3.rendu import objets_moteur

CLASSES = {}


def classe(nom, pixels):
    p = np.asarray(pixels)
    cle = (nom, tuple(sorted(np.unique(p[p >= 0]).tolist())))
    return CLASSES.setdefault(cle, len(CLASSES) + 100)  # ≥ 100 : jamais confondu avec une couleur 0-15


def etat_oracle(env):
    r = objets_moteur(env)
    objs, couches = [], {}
    for s in r["sprites"]:
        p = np.asarray(s["pixels"])
        forme = frozenset((int(x), int(y)) for y, x in zip(*np.nonzero(p >= 0), strict=True))
        if not forme:
            continue
        c = classe(s["nom"], p)
        couches[c] = s["couche"]
        objs.append((c, forme, int(s["x"]), int(s["y"])))
    return tuple(sorted(objs, key=cle_objet)), r, couches


class TrajOracle:
    """Même interface que faits.Trajectoire (etats, actions, taille, cases, fond, exclues, s, ox, oy, atomiques)."""

    def __init__(self, etats, actions, r0, couches):
        self.etats, self.couches = list(etats), couches
        k, (y0, x0, _, _) = r0["echelle"], r0["cadre"]
        self.s, self.ox, self.oy = k, x0, y0
        h, w = r0["vue"]
        self.taille, self.fond, self.exclues, self.atomiques = (w, h), -1, frozenset(), frozenset()
        self.actions = [self.action_cases(a) for a in actions]
        self.cases = [self.peindre(e) for e in self.etats]

    def action_cases(self, a):
        if isinstance(a, tuple):
            return ("clic", (a[1] - self.ox) // self.s, (a[2] - self.oy) // self.s)
        return a

    def peindre(self, e):
        """Image des classes (couche la plus haute dessus) : sert aux faits de clic (changement de classe d'un objet)."""
        w, h = self.taille
        g = np.full((h, w), -1, dtype=int)
        for o in sorted(e, key=lambda o: self.couches.get(o[0], 0)):
            for dx, dy in o[1]:
                x, y = o[2] + dx, o[3] + dy
                if 0 <= x < w and 0 <= y < h:
                    g[y, x] = o[0]
        return g


def segments_oracle(gid, dossier, actions):
    """Comme jeux.segments, mais avec les états oracle ; renvoie [{traj, finale, issue, niveau}]."""
    env = environnement(gid, dossier)
    f = env.reset()
    e, r, couches = etat_oracle(env)
    segs, etats, acts, r0 = [], [e], [], r
    for a in map(en_pixels, actions):
        n0 = f.levels_completed
        f = jouer_action(env, a)
        issue = ("gagne" if f.state == GameState.WIN else "perdu" if f.state == GameState.GAME_OVER
                 else "niveau" if f.levels_completed > n0 else None)
        if issue:
            segs.append({"traj": TrajOracle(etats, acts, r0, couches), "finale": a, "issue": issue, "niveau": n0})
            if issue == "gagne":
                return segs
            if issue == "perdu":
                f = env.step(GameAction.RESET)
            e, r0, c2 = etat_oracle(env)
            couches.update(c2)
            etats, acts = [e], []
        else:
            e, _, c2 = etat_oracle(env)
            couches.update(c2)
            etats.append(e)
            acts.append(a)
    segs.append({"traj": TrajOracle(etats, acts, r0, couches), "finale": None, "issue": None, "niveau": f.levels_completed})
    return segs
