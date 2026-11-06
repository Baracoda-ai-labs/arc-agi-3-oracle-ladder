"""Buts candidats multiples, chacun avec son estimateur de progrès ; un but n'est abandonné que s'il est réfuté
(son estimateur atteint ~1 sans victoire).

  forme   : un mobile rejoint un objet immobile de même forme (emboîter / recouvrir)      [agent_p1.progres]
  modele  : une toile modifiée ressemble de plus en plus à un modèle immobile (reproduire un motif) [agent_p1.progres]
  elim:c  : des objets d'une couleur disparaissent (éliminer) ; progrès = part disparue
(« atteindre » et « pousser sur une cible » sont traités par le modèle de grille quand il existe.)
"""
import numpy as np
from scipy import ndimage
from agent_p1.progres import Progres
from .perception import fond, S4


def compte_objets(im):
    bg = fond(im); out = {}
    for c in np.unique(im):
        if c == bg:
            continue
        out[int(c)] = ndimage.label(im[1:63, 1:63] == c, S4)[1]
    return out


class Buts:
    def __init__(self, im0):
        self.p = Progres(im0); self.refutes = set()
        self.n0 = {c: n for c, n in compte_objets(im0).items() if 2 <= n <= 30}

    def scores(self, im):
        v, d = self.p.evaluer(im)
        sc = {}
        if d.get('forme') is not None:
            sc['forme'] = d['forme']
        if d.get('modele') is not None:
            sc['modele'] = d['modele']
        if self.n0:
            n = compte_objets(im)
            for c, k0 in self.n0.items():
                k = n.get(c, 0)
                if k < k0:
                    sc[f'elim:{c}'] = 0.5 + 0.5 * (k0 - k) / k0
        return sc

    def neutre(self):
        return 0.5 if getattr(self.p, '_pm', None) else 0.0

    def valeur(self, sc):
        vals = [s for g, s in sc.items() if g not in self.refutes]
        return max(vals) if vals else self.neutre()

    def refuter_si_atteint(self, sc, gagne):
        """Rend True si un but vient d'être réfuté (atteint sans victoire)."""
        if gagne:
            return False
        nouveau = False
        for g, s in sc.items():
            if s >= 0.995 and g not in self.refutes:
                self.refutes.add(g); nouveau = True
        return nouveau
