# SPDX-License-Identifier: MIT-0
"""C (CW-280, variante C) : issues d'un plan pour chaque but actif (victoire prédite au 1er pas où le but est vrai)."""
from chrysalide.arc3.moteur import _issues_plan


class _Th:
    """Théorie jouet : l'objet 1 avance d'une case à droite par coup."""
    def pas(self, monde, a, taille):
        return [(c, f, x + 1, y) if c == 1 else (c, f, x, y) for c, f, x, y in monde], None


def test_issues_plan_departage():
    monde = [(1, ((0, 0),), 0, 0), (2, ((0, 0),), 2, 0), (3, ((0, 0),), 5, 0)]
    buts = [("sortie", 1, 2), ("sortie", 1, 3)]
    assert _issues_plan(_Th(), monde, (8, 1), ["RIGHT"] * 3, buts) == [2, 0]  # le plan départage les deux buts


def test_plan_exact_but_suppose(monkeypatch):
    """Dynamique exacte fournie (simulateur jouet : un point qui avance à droite), but supposé = atteindre la sortie (case 4), que le point RECOUVRE à l'arrivée (CCM-202-B : recouvert = inconnu)."""
    import numpy as np

    import chrysalide.arc3.moteur as M

    class Sim:
        def etat(self):
            return 0

        def pas(self, e, lot):
            return (min(e + 1, 7), False) if lot["action"] == "RIGHT" else (e, False)

        def image(self, e):
            g = np.zeros((64, 64), int)
            g[0, 32] = 5  # cible fixe, recouverte quand le point l'atteint
            g[0, 8 * e] = 3
            return g

        def cle(self, e):
            return e

    class Tr:
        s, ox, oy, fond, exclues = 8, 0, 0, 0, frozenset()

    monkeypatch.setattr(M, "_candidats_buts", lambda th, tr, p=(): [("sortie", 3, 5)])
    but, plan, infos = M._plan_exact(Sim(), None, Tr(), [4, 1], 1000, 0.0, 1e9)
    assert but == ("sortie", 3, 5) and plan == [4, 4, 4, 4] and infos["exact_plans"] == 1
