from chrysalide.arc3.masque import Masque, etat_masque


def grille(joueur, pas, h=12, w=12):
    """Joueur (couleur 3) qui va et vient sur la rangée 6 ; barre de pas (couleur 2 -> 0) sur la rangée 0."""
    g = [[0] * w for _ in range(h)]
    for c in range(w):
        g[0][c] = 2 if c >= pas else 0
    g[6][joueur] = 3
    return g


def test_compteur_masque_joueur_garde():
    m, pos, prec = Masque(min_coups=8), [2, 3, 4, 3, 2, 3, 4, 5, 4, 3, 2, 3], grille(2, 0)
    for i, p in enumerate(pos[1:], start=1):
        g = grille(p, i)
        m.observer(prec, g)
        prec = g
    cel = m.cellules()
    assert all(r == 0 for r, _ in cel) and len(cel) > 0
    assert not any(r == 6 for r, _ in cel)
    # même position du joueur, compteur différent -> même état masqué ; joueur ailleurs -> état différent
    assert etat_masque(grille(3, 4), 1, cel) == etat_masque(grille(3, 9), 1, cel)
    assert etat_masque(grille(3, 4), 1, cel) != etat_masque(grille(4, 4), 1, cel)


def test_trop_peu_de_coups_aucun_masque():
    m = Masque(min_coups=8)
    m.observer(grille(2, 0), grille(3, 1))
    assert m.cellules() == frozenset()
