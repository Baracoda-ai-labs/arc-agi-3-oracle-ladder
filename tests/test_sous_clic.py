# SPDX-License-Identifier: MIT-0
"""Un clic tombé dans le trou qu'enclot une pièce désigne la pièce (ka59 sous CREUX, CCM-067-D)."""
from chrysalide.arc3.logique.theorie import _sous_clic

CADRE = (14, frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1)}, 20, 29)
C_OUVERT = (14, frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1), (2, 1)}, 20, 29)


def test_clic_dans_le_trou():
    assert _sous_clic(CADRE, 21, 30) and _sous_clic(CADRE, 20, 29)
    assert not _sous_clic(CADRE, 25, 30)
    assert not _sous_clic(C_OUVERT, 21, 30)  # trou ouvert sur le bord : pas enclos
