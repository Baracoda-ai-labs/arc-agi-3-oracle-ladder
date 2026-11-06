# SPDX-License-Identifier: MIT-0
"""CW-220 : liste ordonnée d'hypothèses → poids des familles de lois dans l'induction."""
import re

from chrysalide.arc3.logique.induction import faits_poids


def _poids(txt):
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"poids\((\w+),(\d+)\)", txt)}


def test_sans_ordre_tout_a_un():
    assert set(_poids(faits_poids()).values()) == {1}


def test_ordre_rang():
    p = _poids(faits_poids(["transforme", "consomme"]))
    assert p["tr"] == 1 and p["c"] == 2 and p["m"] == 3 and p["l"] == 3
