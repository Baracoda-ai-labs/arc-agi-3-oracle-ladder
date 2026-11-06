# SPDX-License-Identifier: MIT-0
"""Marques relevées par les centres des cadres 3 × 3 (re86 N5, CCM-275-C) : cadres entiers, et cadre coupé par une pièce
(fragments sur l'anneau d'un même centre) ; couleur du point central, -1 s'il est caché."""
from chrysalide.arc3.logique.induction import centres_cadres

ANNEAU = frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1)}
COLONNE = frozenset({(0, 0), (0, 1), (0, 2)})


def test_centres_cadres():
    etat = [(4, ANNEAU, 0, 0), (9, frozenset({(0, 0)}), 1, 1), (4, ANNEAU, 10, 0), (8, frozenset({(0, 0)}), 11, 1),
            (4, COLONNE, 20, 0), (4, COLONNE, 22, 0),  # cadre coupé (haut et bas cachés), centre (21, 1) caché
            (4, COLONNE, 30, 0)]                       # fragment isolé : pas un cadre
    assert centres_cadres(etat) == {(1, 1): 9, (11, 1): 8, (21, 1): -1}
