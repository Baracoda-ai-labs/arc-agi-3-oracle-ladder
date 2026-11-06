# SPDX-License-Identifier: MIT-0
"""E (CCM-042-E), écrit par C : but « centre » = centre de la boîte d'un objet a (≥ 3 cases) à ≤ 1 case d'un petit objet
b (≤ 2 cases), distinct ; même verdict dans la théorie et dans le programme exporté."""
from chrysalide.arc3.logique.theorie import Theorie

JOUEUR = frozenset((x, y) for x in range(2) for y in range(3))  # 2 × 3, comme g50t
POINT = frozenset({(0, 0)})


def _monde(jx, jy):
    return ((9, JOUEUR, jx, jy), (9, POINT, 6, 6))


def test_centre_theorie():
    but = ("centre", 9, 9)
    assert Theorie._vrai(but, _monde(5, 5))       # centre (5,5 ; 6) : à une case du point
    assert Theorie._vrai(but, _monde(6, 5))
    assert not Theorie._vrai(but, _monde(1, 1))
    assert not Theorie._vrai(but, ((9, JOUEUR, 5, 5),))  # le joueur seul n'est pas « un petit objet distinct »


def test_centre_exporte_comme_la_theorie():
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    th = Theorie(but=("centre", 9, 9))
    prog, non = exporter(th, (12, 12))
    assert not non
    for (jx, jy) in [(5, 5), (6, 5), (1, 1), (8, 8), (4, 6)]:
        sc = Scene((12, 12), 0, 0, [_sprite(o) | {"visible": True} for o in _monde(jx, jy)])
        Programme(prog).step(sc, ("UP",))
        assert (getattr(sc, "issue", None) is not None) == Theorie._vrai(th.but, _monde(jx, jy)), (jx, jy)


def test_ordre_des_candidats_centre(monkeypatch):
    """CCM-046-E : centre(a, b) écarté si b n'a pas de petit objet, reculé si son petit objet est une interface (bord ou
    changeant), sinon du plus loin au plus près du départ de l'acteur."""
    from types import SimpleNamespace

    from chrysalide.arc3.moteur import _ordre_centre
    monkeypatch.setenv("CHRYS_BUT_CENTRE", "1")
    sol = frozenset((x, y) for x in range(3) for y in range(3))
    e = ((9, JOUEUR, 2, 2), (1, POINT, 0, 0), (7, POINT, 10, 10), (5, sol, 5, 5))
    tr = SimpleNamespace(etats=[e, e], taille=(16, 16))
    cands = [("sortie", 9, 1), ("centre", 9, 1), ("centre", 9, 5), ("centre", 9, 7), ("ancre", 9, 1)]
    assert _ordre_centre(cands, tr) == [("sortie", 9, 1), ("centre", 9, 7), ("centre", 9, 1), ("ancre", 9, 1)]
    monkeypatch.setenv("CHRYS_BUT_CENTRE", "0")
    assert _ordre_centre(cands, tr) == cands


def test_ordre_centre_acteur(monkeypatch):
    """CCM-047-E : acteur sans objet d'au moins 3 cases → écarté ; acteur dans la bande du bord (jauge) → reculé."""
    from types import SimpleNamespace

    from chrysalide.arc3.moteur import _ordre_centre
    monkeypatch.setenv("CHRYS_BUT_CENTRE", "1")
    barre = frozenset((x, 0) for x in range(6))
    e = ((9, JOUEUR, 4, 4), (2, barre, 0, 0), (4, POINT, 1, 5), (7, POINT, 10, 10))
    tr = SimpleNamespace(etats=[e, e], taille=(16, 16))
    cands = [("centre", 2, 7), ("centre", 9, 7), ("centre", 4, 7)]
    assert _ordre_centre(cands, tr) == [("centre", 9, 7), ("centre", 2, 7)]
