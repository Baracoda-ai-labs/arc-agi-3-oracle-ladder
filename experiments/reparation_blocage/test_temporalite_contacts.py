import pytest
from temporalite_contacts import delais_compatibles, resumer


def test_animation_non_calibree_ne_refute_pas():
    for t in (14, 15):
        r = delais_compatibles([t], [(16, 16)])
        assert r["delais_conditionnels"] == [16 - t]
        assert not r["refutation_autorisee"]


def test_calibration_independante_departage():
    assert delais_compatibles([14], [(16, 16)], {1})["refutation_autorisee"]
    assert not delais_compatibles([15], [(16, 16)], {1})["refutation_autorisee"]


def test_censure_et_intervalle():
    assert delais_compatibles([None], [None])["delais_conditionnels"] is None
    assert delais_compatibles([3, 4], [(4, 6), (6, 7)])["delais_conditionnels"] == [2, 3]
    with pytest.raises(ValueError):
        delais_compatibles([1], [(3, 2)])


def test_perte_de_controle_ne_devient_pas_contact_negatif():
    fs = [
        {"controle_visible": v, "regles": {"a": {"active": a}, "b": {"active": b}}}
        for v, a, b in [(True, False, False), (True, True, False), (True, True, True), (False, False, False)]
    ]
    r = resumer(fs, ["a", "b"])
    assert r["premiere_activation"] == {"a": 1, "b": 2}
    assert r["pertes_reconnaissance"] == [3]
    assert r["horloge_issue_sdk"] == "fin_action_seulement"
