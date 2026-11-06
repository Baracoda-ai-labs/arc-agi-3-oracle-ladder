"""D (CHRYS_CREUX, ka59) : un cadre d'un pixel autour d'un trou est détecté ; la trajectoire passe alors à l'échelle 1."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire, creux


def _image():
    g = np.full((64, 64), 2)
    for y0 in range(0, 64, 4):  # grands blocs 4×4 de deux couleurs : l'échelle choisie est 4
        for x0 in range(0, 64, 4):
            g[y0:y0 + 4, x0:x0 + 4] = 2 if (y0 + x0) % 8 else 1
    g[20:25, 20:25] = 4
    g[21:24, 21:24] = 1  # cadre 5×5 de couleur 4, creux 3×3
    return g


def test_cadre_creux_detecte():
    assert any(c == 4 and t == 9 for c, _b, t in creux(_image(), 4))


def test_echelle_1_sous_le_drapeau(monkeypatch):
    g = _image()
    monkeypatch.delenv("CHRYS_CREUX", raising=False)
    s0 = Trajectoire([g, g], [1]).s
    monkeypatch.setenv("CHRYS_CREUX", "1")
    tr = Trajectoire([g, g], [1])
    assert s0 > 1 and tr.s == 1 and tr.creux


def test_absorber_trous_couleur():
    from chrysalide.arc3.logique.faits import absorber_trous
    cadre = frozenset((x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1))
    def etat(x0, c_trou):
        return ((2, cadre, x0, 0), (c_trou, frozenset({(0, 0)}), x0 + 1, 1))
    autre = absorber_trous([etat(0, 0), etat(5, 0)], fond=3)  # trou d'une autre couleur : gardé (CCM-263-C)
    assert all(len(e) == 2 for e in autre)
    meme = absorber_trous([etat(0, 2), etat(5, 2)], fond=3)  # trou de la couleur de l'hôte : fusionné
    assert all(len(e) == 1 and len(e[0][1]) == 9 for e in meme)
