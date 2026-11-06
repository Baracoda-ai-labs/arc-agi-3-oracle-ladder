# SPDX-License-Identifier: MIT-0
"""C (CCM-140-C) : but `copie` — grille de tuiles cliquables à rendre égale à la miniature statique (détecteur de D)."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import buts_copie
from chrysalide.arc3.logique.theorie import Theorie


def _images():
    cible = [[12, 12, 12], [12, 13, 12], [12, 12, 12]]
    g = np.zeros((64, 64), int)
    for i in range(3):
        for j in range(3):
            g[10 + 6 * i:14 + 6 * i, 20 + 6 * j:24 + 6 * j] = 13 if (i + j) % 2 else 12
            g[56 + 2 * i:58 + 2 * i, 2 + 2 * j:4 + 2 * j] = cible[i][j]
    g[54, 0:10] = g[63, 0:10] = g[54:64, 0] = g[54:64, 9] = 7
    g2 = g.copy()
    g2[10:14, 20:24] = 13  # deux clics basculent les tuiles (0, 0) puis (1, 1)
    g3 = g2.copy()
    g3[16:20, 26:30] = 13
    return [g, g2, g3], cible


def test_but_copie_trouve_et_verifie():
    imgs, cible = _images()
    tr = Trajectoire(imgs, [("CLICK", 12, 22), ("CLICK", 17, 27)], ech=(1, 0, 0))
    buts = buts_copie([(tr,)])
    assert len(buts) == 1 and buts[0][0] == "copie"
    assert not Theorie._vrai(buts[0], tr.etats[-1])
    fini = imgs[-1].copy()
    for i in range(3):
        for j in range(3):
            fini[10 + 6 * i:14 + 6 * i, 20 + 6 * j:24 + 6 * j] = cible[i][j]
    tr2 = Trajectoire([imgs[-1], fini], [("CLICK", 12, 22)], ech=(tr.s, tr.ox, tr.oy))
    assert Theorie._vrai(buts[0], tr2.etats[-1])


def test_sans_clic_pas_de_but():
    imgs, _ = _images()
    assert buts_copie([(Trajectoire([imgs[0], imgs[0]], ["UP"], ech=(1, 0, 0)),)]) == []


def test_copie_exportee():
    """Le but `copie` exporté dans le langage est vrai exactement quand chaque case a la couleur du modèle."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import _condition_but
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    but = ("copie", ((12, ((0, 0),)), (13, ((1, 0),))), None)
    cond = _condition_but(but)

    def vrai(c0, c1):
        sc = Scene((1, 2), 0, 0, [_sprite((c0, frozenset({(0, 0)}), 0, 0)) | {"visible": True},
                                  _sprite((c1, frozenset({(0, 0)}), 1, 0)) | {"visible": True}])
        p = Programme({"regles": []})
        return bool(p.ev(cond, {"_scene": sc, "_action": None, "_niveau": 0, "_debut": False}))
    assert vrai(12, 13) and not vrai(13, 13)
