"""D (CHRYS_TRAITS_FINS, CCM-206-C) : à l'échelle 2, un point d'un pixel hors du coin haut-gauche de son bloc survit."""
import numpy as np

from chrysalide.arc3.logique.faits import cases


def test_point_d_un_pixel(monkeypatch):
    g = np.full((64, 64), 5)
    g[21, 11] = 9                       # bloc (10, 5) à l'échelle 2 : le point n'est pas au coin haut-gauche
    monkeypatch.delenv("CHRYS_TRAITS_FINS", raising=False)
    assert (cases(g, 2, 0, 0) != 9).all()
    monkeypatch.setenv("CHRYS_TRAITS_FINS", "1")
    c = cases(g, 2, 0, 0)
    assert c[10, 5] == 9 and (c == 9).sum() == 1
