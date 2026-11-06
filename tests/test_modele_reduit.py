"""D (CCM-033-D) : `faits.modele_reduit` retrouve la cible dessinée en miniature (échelle 2, cadre d'une autre couleur)."""
import numpy as np

from chrysalide.arc3.logique.faits import modele_reduit


def _image():
    g = np.zeros((64, 64), int)
    cible = [[12, 12, 12], [12, 13, 12], [12, 12, 12]]
    for i in range(3):
        for j in range(3):
            g[10 + 8 * i:16 + 8 * i, 20 + 8 * j:26 + 8 * j] = 13 if (i + j) % 2 else 12  # tuiles 6 px, état courant
            g[55 + 2 * i:57 + 2 * i, 2 + 2 * j:4 + 2 * j] = cible[i][j]                    # miniature, 2 px par case
    g[54, 1:9] = g[61, 1:9] = g[54:62, 1] = g[54:62, 8] = 7                                  # cadre
    cases = {(i, j): 13 if (i + j) % 2 else 12 for i in range(3) for j in range(3)}
    return g, cases, cible


def test_miniature_trouvee_seule():
    g, cases, cible = _image()
    r = modele_reduit([g, g], cases, exclure=(20, 10, 46, 36))
    assert len(r) == 1 and r[0]["echelle"] == 2 and r[0]["origine"] == (2, 55)
    assert r[0]["grille"] == tuple(map(tuple, cible)) and r[0]["ecarts"] == 5


def test_region_qui_change_rejetee():
    g, cases, _ = _image()
    g2 = g.copy()
    g2[55, 2] = 13  # la « miniature » bouge : ce n'est pas un modèle affiché
    assert not any(x["echelle"] == 2 for x in modele_reduit([g, g2], cases, exclure=(20, 10, 46, 36)))
