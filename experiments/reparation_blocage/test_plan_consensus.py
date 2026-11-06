from types import SimpleNamespace

from plan_consensus import chercher_modele


def test_refuse_desaccord_et_prefere_progres_commun():
    s = ((0, 3), frozenset(), ("continue", "continue"), 0)
    b = SimpleNamespace(
        depart=s,
        start=(0, 3),
        g=-1,
        actions=lambda t: [3, 4] if t[3] == 0 else [],
        pas=lambda t, a: ((0, 0 if a == 3 else 2), t[1], ("continue", "defaite") if a == 3 else t[2], 1),
    )
    assert chercher_modele(b)["plan"] == [4]
    assert chercher_modele(b, interdit={"4"})["plan"] is None
