import pytest
from montecarlo import chercher


@pytest.mark.parametrize('methode', ['nmcs', 'aleatoire'])
def test_chemin_et_cycle(methode):
    def pas(s, a):
        return min(4, s + 1) if a == 'avance' else s

    plan, infos = chercher(0, ['attend', 'avance'], pas, lambda s: s == 4,
                           lambda s: False, lambda s: s, 4, 1,
                           methode=methode, transitions_max=100)
    assert plan == ['avance'] * 4
    assert infos['transitions'] <= 100


@pytest.mark.parametrize('methode', ['nmcs', 'aleatoire'])
def test_budget_et_aucune_fausse_victoire(methode):
    plan, infos = chercher(0, [1, -1], lambda s, a: s + a, lambda s: s == 100,
                           lambda s: s < 0, lambda s: s, 4, 1,
                           methode=methode, transitions_max=17)
    assert plan is None
    assert infos['transitions'] == 17
