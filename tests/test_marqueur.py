# SPDX-License-Identifier: MIT-0
"""C (CCM-102-C, re86) : marqueur de sélection — recollage de l'hôte coupé (perception) et porteur (théorie)."""
import numpy as np

from chrysalide.arc3.logique.faits import MARQUEUR, recoller_marqueurs
from chrysalide.arc3.logique.theorie import Theorie

UN = frozenset({(0, 0)})

CROIX = frozenset({(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)})


def _bras(c, x, y):
    """Croix de couleur c (coin x, y) coupée en son centre par un point 0 : 4 bras + le point."""
    return [(c, frozenset({(0, 0)}), x + 1, y), (c, frozenset({(0, 0)}), x, y + 1), (c, frozenset({(0, 0)}), x + 2, y + 1),
            (c, frozenset({(0, 0)}), x + 1, y + 2), (0, frozenset({(0, 0)}), x + 1, y + 1)]


def test_recollage():
    e = tuple(sorted(_bras(9, 0, 0) + [(11, CROIX, 5, 0)]))
    r = recoller_marqueurs(e)
    assert (9, CROIX, 0, 0) in r and (MARQUEUR, frozenset({(0, 0)}), 1, 1) in r and (11, CROIX, 5, 0) in r
    assert recoller_marqueurs(e, couleurs=frozenset({3})) == e  # couleur de marqueur non retenue : inchangé


def test_porteur():
    m = MARQUEUR
    th = Theorie(moves={(m, 4): (1, 0)}, porteur=(m, 5), hotes=frozenset({(9, CROIX), (11, CROIX)}))
    monde = ((9, CROIX, 0, 0), (11, CROIX, 5, 0), (m, frozenset({(0, 0)}), 1, 1))
    apres, _ = th.pas(monde, 4, (10, 5))  # la flèche déplace le marqueur ET la croix qu'il porte, pas l'autre
    assert (9, CROIX, 1, 0) in apres and (11, CROIX, 5, 0) in apres and (m, frozenset({(0, 0)}), 2, 1) in apres
    saute, _ = th.pas(monde, 5, (10, 5))  # le sélecteur envoie le marqueur au centre de l'autre croix
    assert (m, frozenset({(0, 0)}), 6, 1) in saute and (9, CROIX, 0, 0) in saute


def test_buts_statiques(monkeypatch):
    from chrysalide.arc3.logique.induction import buts_statiques
    un = frozenset({(0, 0)})

    from types import SimpleNamespace
    tr = SimpleNamespace(actions=[4], etats=[((1, un, 0, 0), (7, un, 5, 0)), ((1, un, 1, 0), (7, un, 5, 0))])
    th = Theorie()  # aucune loi : les buts viennent des objets vus changer, pas de th.moves
    buts = buts_statiques(th, [(tr, None, None)])
    assert ("sortie", 1, 7) in buts and th.obligations[("sortie", 1, 7)]["actions_vues"] == ["4"]


def test_couleurs_diagonales():
    import numpy as np

    from chrysalide.arc3.logique.faits import couleurs_diagonales, objets
    g = np.full((6, 6), 5)
    for k in range(4):
        g[k, k] = 12      # ligne diagonale de couleur 12
    g[5, 0] = g[5, 1] = 7  # couleur 7 en bloc horizontal : pas une diagonale
    assert couleurs_diagonales(g, 5) == frozenset({12})
    assert sum(1 for o in objets(g, 5, frozenset(), frozenset({12})) if o[0] == 12) == 1
    assert sum(1 for o in objets(g, 5) if o[0] == 12) == 4
    g[4:6, 3:5] = 12  # re86 N5 : un carré plein de la même couleur ailleurs (légende) n'empêche pas la diagonale
    assert 12 in couleurs_diagonales(g, 5)


def test_selection_cachee():
    from chrysalide.arc3.logique.theorie import VIRTUEL
    th = Theorie(moves={(12, 4): (1, 0), (13, 4): (1, 0)}, selection=(5, (12, 13), 0), debordent=frozenset({13}))
    monde = ((12, UN, 0, 0), (13, UN, 4, 2))
    m1, _ = th.pas(monde, 4, (6, 6))  # sélection initiale : la 12 bouge seule
    assert (12, UN, 1, 0) in m1 and (13, UN, 4, 2) in m1
    m2, _ = th.pas(th.pas(m1, 5, (6, 6))[0], 4, (6, 6))  # sélecteur, puis flèche : c'est la 13 qui bouge
    assert (12, UN, 1, 0) in m2 and (13, UN, 5, 2) in m2 and any(o[0] == VIRTUEL and o[2] == 1 for o in m2)
    assert th.avec_selection(monde, [4, 5, 4])[-1][2] == 1  # sélection courante reconstituée depuis les actions


def test_porteur_exporte():
    """CCM-177-B : le programme exporté suit la théorie (flèche : la croix suit le marqueur ; sélecteur : saut)."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    m = MARQUEUR
    th = Theorie(moves={(m, 4): (1, 0)}, porteur=(m, 5), hotes=frozenset({(9, CROIX), (11, CROIX)}))
    monde = ((9, CROIX, 0, 0), (11, CROIX, 5, 0), (m, frozenset({(0, 0)}), 1, 1))
    prog, non = exporter(th, (10, 5))
    assert not non

    def pose(sc):
        return sorted((int(np.asarray(s["pixels"]).max()), s["x"], s["y"]) for s in sc.sprites)
    for action, nom in ((4, "RIGHT"), (5, "SPACE")):
        sc = Scene((5, 10), 0, 0, [_sprite(o) | {"visible": True} for o in monde])
        Programme(prog).step(sc, (nom,))
        attendu, _ = th.pas(monde, action, (10, 5))
        assert pose(sc) == sorted((o[0], o[2], o[3]) for o in attendu), nom
        # CCM-189-B : le marqueur (trou de fond dans sa pièce) reste dessiné au-dessus de la pièce qui le porte
        couches = {int(np.asarray(s["pixels"]).max()): s.get("couche", 0) for s in sc.sprites}
        assert couches[m] > max(v for k, v in couches.items() if k != m), nom


def test_enroulement():
    """tr87 : un curseur qui dépasse son intervalle revient à l'autre bout (théorie)."""
    th = Theorie(moves={(0, 4): (7, 0), (0, 3): (-7, 0)}, enroule={0: (0, 15, 43)})
    assert th.pas(((0, UN, 43, 5),), 4, (64, 64))[0] == ((0, UN, 15, 5),)
    assert th.pas(((0, UN, 15, 5),), 3, (64, 64))[0] == ((0, UN, 43, 5),)
    assert th.pas(((0, UN, 22, 5),), 4, (64, 64))[0] == ((0, UN, 29, 5),)


def test_marqueur_centre_x_diagonal():
    """re86 N5 : le marqueur au centre d'un X tracé en diagonale (4 bras reliés en coin) est recollé à sa pièce."""
    import numpy as np

    from chrysalide.arc3.logique.faits import couleurs_diagonales, objets, recoller_marqueurs
    g = np.full((9, 9), 5)
    for k in range(-3, 4):
        g[4 + k, 4 + k] = g[4 + k, 4 - k] = 11
    g[4, 4] = 0
    diag = couleurs_diagonales(g, 5)
    e = objets(g, 5, frozenset(), diag)
    assert sum(1 for o in e if o[0] == 11) == 4  # 4 bras séparés par le marqueur
    r = recoller_marqueurs(e, frozenset({0}), diag)
    assert [len(o[1]) for o in r if o[0] == 11] == [13] and any(o[0] == MARQUEUR for o in r)
    assert recoller_marqueurs(e, frozenset({0})) == e  # sans les couleurs diagonales : inchangé


def test_porteuse_creuse(monkeypatch):
    """re86 N5 (CHRYS_PORTEUR_BOITE=1) : marqueur au centre VIDE d'une pièce creuse → la pièce dont la boîte le contient."""
    from chrysalide.arc3.logique.faits import recoller_marqueurs
    from chrysalide.arc3.logique.theorie import porteuse
    anneau = frozenset({(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)})
    piece, point = (14, anneau, 5, 5), (0, frozenset({(0, 0)}), 6, 6)
    monkeypatch.delenv("CHRYS_PORTEUR_BOITE", raising=False)
    assert recoller_marqueurs((point, piece), frozenset({0})) == (point, piece)
    assert porteuse((piece, (MARQUEUR, point[1], 6, 6)), (MARQUEUR, point[1], 6, 6)) is None
    monkeypatch.setenv("CHRYS_PORTEUR_BOITE", "1")
    r = recoller_marqueurs((point, piece), frozenset({0}))
    assert (MARQUEUR, point[1], 6, 6) in r
    assert porteuse(r, (MARQUEUR, point[1], 6, 6)) == piece


def test_saut_sel_appris():
    """re86 N5 : sous le sélecteur, le marqueur va à la pièce de la forme APPRISE, au décalage appris (pivot propre)."""
    a = frozenset({(0, 0), (1, 0), (2, 0)})
    b = frozenset({(0, 0), (0, 1), (0, 2), (1, 1)})
    th = Theorie(porteur=(MARQUEUR, 5), hotes=frozenset({(11, a), (12, b)}), saut_sel=((a, b, (0, 1)),))
    monde = ((11, a, 0, 0), (12, b, 5, 3), (MARQUEUR, frozenset({(0, 0)}), 1, 0))
    res, _ = th.pas(monde, 5, (10, 10))
    assert [(o[2], o[3]) for o in res if o[0] == MARQUEUR] == [(5, 4)]
