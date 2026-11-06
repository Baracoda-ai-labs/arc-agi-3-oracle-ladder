"""D (CW-215) : Masque(court=True) reconnaît une jauge qui s'use sur un niveau de moins de 8 coups, pas un mobile qui longe
le bord ; court=False (défaut, usage de B) : inchangé."""
from chrysalide.arc3.masque import Masque


def _grille(barre, joueur=None):
    g = [[0] * 12 for _ in range(8)]
    for c in range(barre):
        g[0][c] = 4
    if joueur is not None:
        g[0][joueur] = 7
    return g


def test_jauge_courte_masquee():
    m, mc = Masque(), Masque(court=True)
    for k in range(10, 5, -1):  # 5 coups : la barre perd une case à chaque coup
        for x in (m, mc):
            x.observer(_grille(k), _grille(k - 1))
    assert not m.cellules()
    assert {(0, c) for c in range(12)} <= set(mc.cellules())


def test_mobile_le_long_du_bord_non_masque():
    mc = Masque(court=True)
    for x in range(1, 6):  # un mobile avance d'une case par coup sur la rangée 0 : il rechange la case qu'il quitte
        mc.observer(_grille(0, x), _grille(0, x + 1))
    assert not mc.cellules()
