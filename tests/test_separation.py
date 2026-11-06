# SPDX-License-Identifier: MIT-0
"""Séparation garde / recalcule (CW-404) : chaque champ de Theorie est classé ; la théorie du niveau suivant ne garde AUCUNE
coordonnée de l'ancienne scène ; l'échelle change les lois en cases."""
import dataclasses

from chrysalide.arc3.logique.separation import TABLE, pour_niveau_suivant, separer
from chrysalide.arc3.logique.theorie import Theorie

P = frozenset({(0, 0), (1, 0), (0, 1), (1, 1), (2, 2)})


def test_table_complete():
    assert {f.name for f in dataclasses.fields(Theorie)} <= set(TABLE), "champ de Theorie non classé"


def test_niveau_suivant():
    th = Theorie(moves={(281, 4): (3, 0)}, retour=((281, 5, 7, 4),), fantome=(281, 5, 2, 7, 4), formes={281: P},
                 tenue_cases=((5, frozenset({(1, 1)}), frozenset(), frozenset({(9, 9)})),), but=("centre", 281, 9))
    assert "tenue_cases" in separer(th)["observe"]
    gros = frozenset((x * 2 + i, y * 2 + j) for x, y in P for i in range(2) for j in range(2))
    etat = ((9, gros, 25, 19), (9, frozenset({(0, 0)}), 1, 1))
    neuve, info = pour_niveau_suivant(th, etat, ech_avant=2, ech_apres=1)
    assert neuve.moves == {(281, 4): (6, 0)}
    assert neuve.retour == ((281, 5, 25, 19),) and neuve.fantome == (281, 5, 2, 25, 19)
    assert not neuve.tenue_cases and neuve.but is None and info["a_retablir"]
