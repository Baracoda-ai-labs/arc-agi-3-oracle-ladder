# SPDX-License-Identifier: MIT-0
"""F (CW-468, CHRYS_F_ZONE) : zone observée (boîte des cases qui ont changé) et test « hors zone » du planificateur."""
from chrysalide.arc3.logique import plan


def test_zone_observee(monkeypatch):
    a = [(3, frozenset({(0, 0)}), 2, 2), (5, frozenset({(0, 0)}), 9, 9)]
    b = [(3, frozenset({(0, 0)}), 4, 3), (5, frozenset({(0, 0)}), 9, 9)]  # l'objet 3 passe de (2, 2) à (4, 3)
    monkeypatch.delenv("CHRYS_F_ZONE", raising=False)
    plan._ZONE.set(None)
    plan.poser_zone([a, b])
    assert plan._ZONE.get() is None  # éteint : rien n'est posé
    monkeypatch.setenv("CHRYS_F_ZONE", "1")
    plan.poser_zone([a, b])
    assert plan._ZONE.get() == (2, 4, 2, 3)  # l'objet immobile (9, 9) n'élargit pas la zone
    assert not plan._hors_zone([(3, frozenset({(0, 0)}), 3, 2)], (2, 4, 2, 3))
    assert plan._hors_zone([(3, frozenset({(0, 0)}), 3, 1)], (2, 4, 2, 3))  # au-dessus : jamais vu là
