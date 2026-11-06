import pytest
from espace_experiences import partitions


def test_regroupe_regles_equivalentes_et_choisit_partition():
    r = partitions([[0, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 1]])
    assert r["classes_indiscernables"] == [[0, 1], [2, 3]]
    assert r["partitions"][0]["entropie_convention_uniforme"] == 1
    assert r["distance_hamming"][0][1] == 0
    assert r["distance_hamming"][0][2] == 1


def test_pas_de_desaccord_pas_information():
    r = partitions([[0, 0, 0], [1, 1, 1]])
    assert all(p["entropie_convention_uniforme"] == 0 for p in r["partitions"])
    with pytest.raises(ValueError):
        partitions([1, 0])


def test_information_par_cout_acces_et_meme_espace():
    from espace_experiences import classer_experiences

    def e(n, c, access, p):
        return {"id": n, "cout_actions": c, "cout_acces": access, "accessible": True, "predictions": p}

    ps = {"a": 0, "b": 0, "c": 1, "d": 1}
    r = classer_experiences(
        [e("court", 1, 0, ps), e("cher", 1, 15, ps), e("autre", 1, 0, {"a": 0}), e("inutile", 1, 0, dict.fromkeys(ps, 0))], ps, 10
    )
    assert r["choix"]["id"] == "court" and r["choix"]["risque"] == "inconnu"
    assert len(r["refus"]) == 3 and not r["choix"]["droit_action"]


def test_reduction_n_impose_pas_un_modele_et_ne_refute_pas_inconnu():
    from espace_experiences import reduire_espace

    assert reduire_espace({"a": 0, "b": 1}, 2)["statut"] == "hors_couverture"
    assert reduire_espace({"a": 0, "b": None}, 2)["inconnues"] == ["b"]
    r = reduire_espace({"a": 0, "b": 1}, 1)
    assert r["compatibles"] == ["b"] and not r["regle_prouvee"]
