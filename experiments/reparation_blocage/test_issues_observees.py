import numpy as np
from hypotheses_navigation import HypothesesNavigation
from issues_observees import comparer_issue, issue_sdk
from transfert_navigation_bp35 import apprendre

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.langue import depuis_python


def test_contact_conditionnel_perdre_langage_existant():
    text = """from chrysalide_langue import *
PROGRAMME = Programme(regles=[Regle("test", quand=existe(existe(contact_moteur(a,b) for b in objets({"tag":"b"})) for a in objets({"tag":"a"})), alors=[perdre()])])"""
    p = depuis_python(text)

    def obj(x, tag):
        return {"x": x, "y": 0, "pixels": [[1]], "couche": 0, "tags": [tag], "nom": tag, "bloquant": True}

    for x, expected in [(0, "defaite"), (1, None)]:
        sc = Scene((64, 64), 0, 0, [obj(0, "a"), obj(x, "b")])
        Programme(p).step(sc, ("LEFT",))
        assert sc.issue == expected


def test_inconnu_pas_continue_et_baseline_niveau():
    assert comparer_issue("inconnue", "defaite")["issue_conforme"] is None
    assert comparer_issue("continue", "defaite")["issue_conforme"] is False
    assert issue_sdk("GameState.NOT_FINISHED", 1, 1) == "continue"
    assert issue_sdk("GameState.NOT_FINISHED", 2, 1) == "niveau"


def test_fin_enregistree_meme_si_personnage_disparu():
    m, _h, buts, z, _j = apprendre()
    h = HypothesesNavigation(m, buts, clics=(True,))
    active = h.actives()
    h.atms.justifier("plan_couvert", ["g-1_clic1", "couverture_issues"])
    after = np.zeros((64, 64), dtype=int)
    r = h.observer(z["images"][0], 4, after, [after], issue_observee="defaite")
    assert r["issue_observee"] == "defaite" and r["plan_invalide"]
    assert h.actives() == active
    assert not h.atms.tient("plan_couvert", ["g-1_clic1", "couverture_issues"])
