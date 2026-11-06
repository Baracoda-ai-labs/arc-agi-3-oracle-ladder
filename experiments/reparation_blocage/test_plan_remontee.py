from types import SimpleNamespace

from plan_consensus import chercher_modele


def test_but_candidat_peut_etre_horizontal_sans_forcer_verite():
    s = ((0, 1), frozenset(), ("continue",), 0)
    m = SimpleNamespace(
        depart=s, start=(0, 1), g=-1, actions=lambda t: [4] if t[3] == 0 else [], pas=lambda t, a: ((1, 1), t[1], t[2], 1)
    )
    assert chercher_modele(m)["plan"] is None
    assert chercher_modele(m, buts={(1, 1)})["plan"] == [4]
