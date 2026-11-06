# SPDX-License-Identifier: MIT-0
"""C (CW-257, décision de Thomas : « comprendre par la COMPRESSION ») — longueur de description (MDL) d'une théorie.

L(théorie) + L(exceptions | théorie), en bits :
- L(théorie) = nombre de faits de la théorie (`texte()`) × BITS_FAIT ;
- L(exceptions) = pour chaque transition rejouée RECALÉE (chaque pas part de l'état observé), chaque case fausse du rendu
  coûte log2(nombre de cases) + log2(16) bits (où, et quelle couleur).
Le modèle NUL (« rien ne change ») a L = 0 + exceptions de l'image précédente prise pour la suivante : une théorie
COMPRIME l'historique si son L total est plus petit. Une théorie simple et un peu fausse peut ainsi battre une théorie
compliquée qui colle à tout, et une théorie partielle n'a plus besoin d'un seuil arbitraire sur son taux d'explication."""
import math

import numpy as np

BITS_FAIT = 24  # un fait (move(c,a,dx,dy), solide(c), …) : classes, action, vecteur ≈ quelques octets


def longueur_theorie(th):
    return BITS_FAIT * sum(1 for f in th.texte().split(". ") if f.strip())


def bits_case(taille):
    w, h = taille
    return math.log2(max(2, w * h)) + 4.0


def longueur_exceptions(th, tr):
    """Bits pour corriger le rejeu recalé de `th` sur `tr` (cases fausses, masque d'interface exclu)."""
    b, n = bits_case(tr.taille), 0
    masque = np.zeros(np.asarray(tr.cases[0]).shape, dtype=bool)
    for r, c in tr.exclues:
        if 0 <= r < masque.shape[0] and 0 <= c < masque.shape[1]:
            masque[r, c] = True
    for t, a in enumerate(tr.actions):
        pred, _ = th.pas(tr.etats[t], a, tr.taille)
        rd = np.asarray(th.rendu(pred, tr.taille, tr.fond))
        vu = np.asarray(tr.cases[t + 1])
        if rd.shape == vu.shape:
            n += int(((rd != vu) & ~masque).sum())
    return b * n


def longueur_nulle(tr):
    """Modèle « rien ne change » : chaque case qui change d'une image à la suivante est une exception."""
    b, n = bits_case(tr.taille), 0
    for t in range(len(tr.actions)):
        a, c = np.asarray(tr.cases[t]), np.asarray(tr.cases[t + 1])
        n += int((a != c).sum())
    return b * n


def mdl(th, tr):
    """→ (L total, L théorie, L exceptions) en bits."""
    lt, le = longueur_theorie(th), longueur_exceptions(th, tr)
    return lt + le, lt, le


def comprime(th, tr):
    """La théorie comprime-t-elle l'historique mieux que le modèle nul ? → (oui, L théorie + exceptions, L nul)."""
    total, _, _ = mdl(th, tr)
    nul = longueur_nulle(tr)
    return total < nul, total, nul
