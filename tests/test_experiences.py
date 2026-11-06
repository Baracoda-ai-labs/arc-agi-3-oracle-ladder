# SPDX-License-Identifier: MIT-0
"""Expériences tirées du menu (CW-365.1) : une hypothèse absente de la théorie donne une expérience exécutable (objets,
trajet, actions, prédictions, coût) ; une hypothèse déjà dans la théorie n'en donne pas."""
from chrysalide.arc3.logique.menu_mecanismes import experiences
from chrysalide.arc3.logique.theorie import Theorie

CARRE = frozenset((x, y) for x in range(2) for y in range(2))


def test_jumeau_cliquer_puis_fleche():
    th = Theorie(moves={(5, 4): (2, 0), (5, 3): (-2, 0), (5, 1): (0, -2), (5, 2): (0, 2)})
    etat = ((5, CARRE, 0, 0), (5, CARRE, 6, 0))  # piloté + jumeau de même forme
    ex = experiences(th, etat, (10, 10))
    sel = [e for e in ex if e["hypothese"] == "selection_au_clic"]
    assert sel and sel[0]["objets"] == [1] and sel[0]["actions"][0][0] == "clic" and sel[0]["cout_total"] == 2
    pousse = [e for e in ex if e["hypothese"] == "pousser"][0]
    assert pousse["preparation"] == 2 and pousse["actions"] == [4]  # trajet de 2 pas avant le contact, puis RIGHT
    th2 = Theorie(moves=th.moves, selection_clic=(5, 0, 0))
    assert not [e for e in experiences(th2, etat, (10, 10)) if e["hypothese"] == "selection_au_clic"]
