from types import SimpleNamespace

import numpy as np
from surface_nouvelle import proposer


def test_classe_nouvelle_laterale_pas_connue_ni_sans_offre():
    grid = np.array([[0, 0, 0], [0, 0, 8], [0, 9, 0]])
    m = SimpleNamespace(sol=0, cassables=set(), pas=2, lire=lambda im: (grid, (1, 1), (0, 0)))
    g = np.zeros((64, 64), dtype=int)
    assert proposer(g, m, {0}, [6], set())["plan"] == [["clic", 5, 3]]
    assert proposer(g, m, {0, 8}, [6], set()) is None
    assert proposer(g, m, {0}, [3, 4], set()) is None
