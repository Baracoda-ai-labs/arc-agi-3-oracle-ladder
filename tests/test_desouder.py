"""D (CHRYS_DESOUDER, re86 N5) : deux pièces distinctes à t-1, soudées au contact à t (l'une repeinte) → recoupées."""
from chrysalide.arc3.logique.faits import desouder


def _obj(col, cases):
    x0, y0 = min(x for x, _ in cases), min(y for _, y in cases)
    return (col, frozenset((x - x0, y - y0) for x, y in cases), x0, y0)


def test_soudure_recoupee_et_mobile_garde():
    fixe = {(0, 0), (1, 0), (0, 1), (1, 1)}
    x_ = {(3, 0), (4, 1), (3, 2), (5, 0), (5, 2)}  # pièce diagonale, autre couleur avant
    autre = {(7, 1), (8, 1), (7, 2), (8, 2), (9, 2)}  # 2e pièce fixe, à droite
    t0 = (_obj(14, fixe), _obj(11, x_), _obj(14, autre))
    bouge = {(x + 1, y) for x, y in x_}  # elle avance d'une case, touche les deux pièces fixes et prend leur couleur
    t1 = (_obj(14, fixe | bouge | autre),)
    out = desouder([t0, t1])
    assert sorted(len(o[1]) for o in out[1]) == [4, 5, 5] and all(o[0] == 14 for o in out[1])
    assert any(o[2:] == (4, 0) for o in out[1])  # la pièce mobile, à sa nouvelle place


def test_rien_a_recouper():
    a = (_obj(3, {(0, 0), (1, 0)}),)
    assert desouder([a, a]) == [a, a]
