# SPDX-License-Identifier: MIT-0
"""C (CW-333) : la jauge comme loi induite. Chaque action consomme un coup ; à 0, défaite ; un coup gagnant reste gagnant."""
import numpy as np

from chrysalide.arc3.logique.theorie import MEM_JAUGE, Theorie

UN = frozenset({(0, 0)})


def test_jauge_theorie(monkeypatch):
    monkeypatch.setenv("CHRYS_JAUGE_ETAT", "1")
    th = Theorie(moves={(3, 4): (1, 0)}, jauge=(2, 1.0))
    m = ((3, UN, 0, 0),)
    m, _ = th.pas(m, 4, (8, 8))
    assert not th.meurt(m) and [o[2] for o in m if o[0] == MEM_JAUGE] == [1]
    m, _ = th.pas(m, 4, (8, 8))
    assert th.meurt(m)
    assert "jauge(2,1)." in th.texte()
    assert th.rendu(m, (8, 8), 0)[0, 2] == 3  # l'objet virtuel n'est pas dessiné


def _scene():
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    return Scene((8, 8), 0, 0, [_sprite(o) | {"visible": True} for o in ((3, UN, 0, 0), (6, UN, 2, 0))])


def test_jauge_exportee():
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    th = Theorie(moves={(3, 4): (1, 0)}, jauge=(2, 1.0))
    prog, non = exporter(th, (8, 8))
    assert not non and prog["etat"]["jauge"] == 2
    p, sc = Programme(prog), _scene()
    p.step(sc, ("RIGHT",))
    assert getattr(sc, "issue", None) is None
    p.step(sc, ("RIGHT",))
    assert sc.issue == "defaite"
    th.but = ("sortie", 3, 6)  # le 2e pas atteint la sortie en vidant la jauge : victoire (coup gagnant gratuit)
    prog, _ = exporter(th, (8, 8))
    p, sc = Programme(prog), _scene()
    p.step(sc, ("RIGHT",))
    p.step(sc, ("RIGHT",))
    assert sc.issue in ("niveau", "victoire")


def test_jauge_lue_sur_la_barre():
    """Barre de 12 cases qui perd une case tous les 2 coups (ligne 63, hors jeu) : rythme 2, réserve au bout."""
    from chrysalide.arc3.logique.faits import Trajectoire
    from chrysalide.arc3.logique.induction import trouver_jauge
    imgs, acts = [], []
    for t in range(13):
        g = np.zeros((64, 64), int)
        g[63, 10:22 - t // 2] = 11
        g[20, 20 + t] = 3
        imgs.append(g)
        if t:
            acts.append(4)
    tr = Trajectoire(imgs, acts)
    th = Theorie(moves={(3, 4): (1, 0)})
    trouver_jauge(th, [(tr, None, None)])
    assert th.jauge == (6, 1.71)  # rythme prudent 12 / (6 + 1) ; 6 cases × 1,71 = 10, moins deux cases de barre
