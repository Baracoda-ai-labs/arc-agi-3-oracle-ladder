# SPDX-License-Identifier: MIT-0
"""Pièce repeinte au contact d'une palette (re86 N5, CCM-270-C) : elle prend la couleur, garde sa forme ; une palette
n'est jamais repeinte ; sans contact, rien ne change."""
from chrysalide.arc3.logique.theorie import Theorie

PIECE = frozenset({(0, 0), (1, 1), (2, 2)})
CARRE = frozenset((x, y) for x in range(2) for y in range(2))


def test_peindre():
    th = Theorie(moves={(283, 3): (-1, 0)}, peint_contact=frozenset({(8, CARRE)}))
    pal = (8, CARRE, 0, 0)
    monde = ((283, PIECE, 3, 0), pal)
    apres, _ = th.pas(monde, 3, (10, 10))
    assert (496 + 8, PIECE, 2, 0) in apres and pal in apres  # arrivée au contact : couleur 8, même forme
    loin = ((283, PIECE, 7, 0), pal)
    apres, _ = th.pas(loin, 3, (10, 10))
    assert (283, PIECE, 6, 0) in apres  # pas de contact : inchangée
