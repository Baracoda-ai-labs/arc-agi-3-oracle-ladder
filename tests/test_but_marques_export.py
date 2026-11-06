# SPDX-License-Identifier: MIT-0
"""But `marques` exporté (CCM-035-G) : le langage dit vrai exactement quand theorie.marques_manquantes == 0 ;
une forme de but sans traduction est signalée en non-exporté, jamais exportée en « faux » muet."""
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.export_langage import _condition_but
from chrysalide.arc3.logique.theorie import marques_manquantes
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene

BUT = ("marques", ((4, ((1, 0), (2, 0))),))


def _vrai(monde):
    sc = Scene((1, 4), 0, 0, [_sprite(o) | {"visible": True} for o in monde])
    return bool(Programme({"regles": []}).ev(_condition_but(BUT), {"_scene": sc, "_action": None, "_niveau": 0,
                                                                   "_debut": False}))


def test_marques_exporte_comme_theorie():
    marques = [(4, frozenset({(0, 0)}), 1, 0), (4, frozenset({(0, 0)}), 2, 0)]
    piece = (11, frozenset({(0, 0), (1, 0)}), 1, 0)       # couvre les deux marques
    demi = (11, frozenset({(0, 0), (1, 0)}), 2, 0)        # n'en couvre qu'une
    seul = (11, frozenset({(0, 0)}), 1, 0)                # objet d'une case : ne compte pas
    marqueur = (512, frozenset({(0, 0), (1, 0)}), 1, 0)   # classe marqueur : ne compte pas
    for monde in ([*marques], [*marques, piece], [*marques, demi], [*marques, demi, seul], [*marques, marqueur]):
        assert _vrai(monde) == (marques_manquantes(monde, BUT[1]) == 0), monde
    assert _vrai([*marques, piece])


def test_but_inconnu_signale():
    assert _condition_but(("inexistant", ())) is None


def test_marques_couleur():
    """« paires colorées » (CCM-059-E) : la pièce qui couvre la marque doit en avoir la couleur (classe 268 = couleur 12)."""
    but = ("marques", ((4, ((1, 0), (2, 0))),), "couleur")
    marques = [(4, frozenset({(0, 0)}), 1, 0), (4, frozenset({(0, 0)}), 2, 0)]

    def vrai(monde):
        sc = Scene((1, 4), 0, 0, [_sprite(o) | {"visible": True} for o in monde])
        return bool(Programme({"regles": []}).ev(_condition_but(but), {"_scene": sc, "_action": None, "_niveau": 0,
                                                                       "_debut": False}))
    for piece in [(4, frozenset({(0, 0), (1, 0)}), 1, 0), (11, frozenset({(0, 0), (1, 0)}), 1, 0),
                  (260, frozenset({(0, 0), (1, 0)}), 1, 0), (268, frozenset({(0, 0), (1, 0)}), 1, 0)]:
        monde = [*marques, piece]
        attendu = marques_manquantes(monde, but[1], True) == 0
        assert vrai(monde) == attendu, piece
        assert attendu == (piece[0] % 16 == 4)
    assert marques_manquantes([*marques, (11, frozenset({(0, 0), (1, 0)}), 1, 0)], but[1]) == 0  # sans couleur : couvert
