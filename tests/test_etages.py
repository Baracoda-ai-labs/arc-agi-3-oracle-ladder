"""Contrôle des trois étages (CW-132) : aucune loi ne cite une donnée propre à un niveau."""
from chrysalide.arc3.etages import echappatoires_niveau


def test_lois_communes_sans_echappatoire():
    prog = {"niveau": {"0": {"cout": 2}, "*": {"cout": 1}},
            "regles": [{"nom": "jauge", "alors": [["consommer", "j", ["param", "cout"]]]},
                       {"nom": "suite", "quand": ["dernier_niveau"], "alors": [["poser", "n", ["niveau"]]]},
                       {"nom": "calc", "quand": ["=", ["%", ["niveau"], "$k"], 0], "alors": []}]}
    assert echappatoires_niveau(prog) == []


def test_motifs_detectes():
    prog = {"au_debut": [["si_alors", ["=", ["niveau"], 3], [["poser", "a", 1]]]],
            "mots": {"cible": {"params": [], "corps": ["elem", ["liste", 4, 7, 9], ["niveau"]]}},
            "regles": [{"nom": "a", "quand": [">=", 2, ["niveau"]], "alors": []},
                       {"nom": "b", "soit": {"c": ["table", {"0": 5, "1": 6}, ["niveau"]]}, "alors": []},
                       {"nom": "c", "soit": {"c": ["elem", [[1, 2], [3, 4]], ["+", ["niveau"], 1]]}, "alors": []},
                       {"nom": "d", "quand": ["contient", ["liste", 0, 2], ["niveau"]], "alors": []},
                       {"alors": [["poser", "x", ["si", ["niveau"], 1, 2]]]}]}
    e = echappatoires_niveau(prog)
    assert [r for r, _ in e] == ["a", "b", "c", "d", "regles[4]", "au_debut[0]", "mot cible"]
    assert "table" in dict(e)["b"] and "comparaison" in dict(e)["a"]
