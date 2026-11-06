# SPDX-License-Identifier: MIT-0
"""C (CW-249, action 2) : élagage des impasses « coin de Sokoban » dans plan.planifier (CHRYS_IMPASSES=1)."""
from chrysalide.arc3.logique.plan import impasse, planifier
from chrysalide.arc3.logique.theorie import Theorie

UN = frozenset({(0, 0)})
MOVES = {(1, 1): (0, -1), (1, 2): (0, 1), (1, 3): (-1, 0), (1, 4): (1, 0)}


def _th():
    return Theorie(moves=dict(MOVES), poussables=frozenset({3}), solides=frozenset({9}), but=("remplir", 3, 5))


def test_coin_hors_cible_est_une_impasse():
    th = _th()
    assert impasse(th, ((3, UN, 0, 0), (5, UN, 4, 4)), (6, 6), {})        # coin de la grille, cible ailleurs
    assert not impasse(th, ((3, UN, 0, 2), (5, UN, 4, 4)), (6, 6), {})    # contre un seul bord : pas une impasse
    assert not impasse(th, ((3, UN, 0, 0), (5, UN, 0, 0)), (6, 6), {})    # dans le coin MAIS sur la cible


def test_elagage_garde_le_plan_et_reduit_la_recherche(monkeypatch):
    th, monde = _th(), ((1, UN, 2, 3), (3, UN, 2, 2), (5, UN, 2, 0))       # pousser la caisse vers le haut, sur la cible
    acts = [1, 2, 3, 4]
    monkeypatch.delenv("CHRYS_IMPASSES", raising=False)
    plan0, n0 = planifier(th, monde, (6, 6), acts)
    monkeypatch.setenv("CHRYS_IMPASSES", "1")
    plan1, n1 = planifier(th, monde, (6, 6), acts)
    assert plan0 == plan1 == [1, 1] and n1 <= n0
