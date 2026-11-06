from types import SimpleNamespace

from branche_retour import chercher


def test_prefere_branche_reversible_et_exclut_ancienne():
    start = ((0, 1), frozenset(), ("continue",), 0)

    def actions(s):
        if s[3] >= 16:
            return []
        return [a for a in (3, 4) if 0 <= s[0][0] + (-1 if a == 3 else 1) <= 2]

    def pas(s, a):
        return ((s[0][0] + (-1 if a == 3 else 1), 1), s[1], s[2], s[3] + 1)

    m = SimpleNamespace(depart=start, start=(0, 1), actions=actions, pas=pas)
    r = chercher(m)
    assert r["plan"] == [4, 4] and r["retour"] == [3, 3]
    assert chercher(m, interdits={"4"})["plan"] is None


def test_refuse_branche_si_retrait_predirait_defaite():
    start = ((0, 1), frozenset(), ("continue",), 0)

    def actions(s):
        return [4] if s[0][0] == 0 else [3]

    def pas(s, a):
        return ((1 if a == 4 else 0, 1), s[1], ("continue",) if a == 4 else ("defaite",), s[3] + 1)

    m = SimpleNamespace(depart=start, start=(0, 1), actions=actions, pas=pas)
    assert chercher(m)["plan"] is None
