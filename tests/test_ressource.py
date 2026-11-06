# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — planification à ressource (logique/ressource.py) et branchement MoteurCle (CW-145)."""
from chrysalide.arc3.logique.ressource import plan_ressource


class Couloir:
    """Modèle jouet : le mobile (classe 0) va à gauche (3) / droite (4) dans un couloir de largeur w."""

    def __init__(self, w):
        self.w = w

    def pas(self, monde, a, taille):
        out = []
        for o in monde:
            if o[0] == 0:
                x = min(self.w - 1, max(0, o[2] + {3: -1, 4: 1}.get(a, 0)))
                o = (o[0], o[1], x, o[3])
            out.append(o)
        return tuple(out), None


MOB = (0, frozenset({(0, 0)}), 0, 0)


def test_porte_directe():
    p = plan_ressource(Couloir(6), (MOB,), (6, 1), MOB, [3, 4], (5, 0), set(), set(), 0, 10, 10)
    assert p == [4] * 5


def test_jauge_courte_refuse_puis_recharge():
    th = Couloir(6)
    assert plan_ressource(th, (MOB,), (6, 1), MOB, [3, 4], (5, 0), set(), set(), 0, 4, 4) is None
    assert plan_ressource(th, (MOB,), (6, 1), MOB, [3, 4], (5, 0), set(), {(2, 0)}, 0, 4, 4) == [4] * 5


def test_passages_sur_modificateur():
    # il faut passer 2 fois sur le modificateur en (1, 0) avant d'entrer sur la porte
    p = plan_ressource(Couloir(4), (MOB,), (4, 1), MOB, [3, 4], (3, 0), {(1, 0)}, set(), 2, 20, 20)
    assert p is not None and sum(1 for i in range(len(p)) if p[:i + 1].count(4) - p[:i + 1].count(3) == 1) >= 2


def test_exploration_sans_energie():
    # exploration : la jauge peut tomber à 0 en route (vie sacrifiée), mais il faut une recharge candidate avant la porte
    th = Couloir(6)
    assert plan_ressource(th, (MOB,), (6, 1), MOB, [3, 4], (5, 0), set(), set(), 0, 2, 2) is None
    assert plan_ressource(th, (MOB,), (6, 1), MOB, [3, 4], (5, 0), set(), {(4, 0)}, 0, None, 2) == [4] * 5
    assert plan_ressource(th, (MOB,), (6, 1), MOB, [3, 4], (5, 0), set(), set(), 0, None, 2) == [4] * 5


def test_moteur_cle_se_tait_sans_historique():
    from chrysalide.arc3.logique.moteur_cle import MoteurCle
    m = MoteurCle(budget=1)
    assert m.proposer({"grilles": [], "lots": [], "precedents": []}) is None
