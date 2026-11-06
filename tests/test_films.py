"""D (CHRYS_FILMS, CW-306) : film de chaque coup simple dans hist["films"] (aligné sur les lots) ; compacté ; éteint =
historique inchangé."""
import numpy as np

from chrysalide.arc3.branche import _compacter


def test_compacter():
    a, b = np.zeros((4, 4), int), np.ones((4, 4), int)
    assert _compacter(None) is None and _compacter([a]) is None and _compacter([a, a]) is None
    f = _compacter([a, a, b, b, a])
    assert len(f) == 3 and f[0].dtype == np.uint8 and (f[1] == 1).all()
    long = [np.full((2, 2), k % 2) for k in range(300)]
    g = _compacter(long, plafond=10)
    assert len(g) == 10 and (g[0] == long[0]).all() and (g[-1] == long[-1]).all()
