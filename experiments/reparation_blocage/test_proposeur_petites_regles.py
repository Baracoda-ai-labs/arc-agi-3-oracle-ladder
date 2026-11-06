import copy

import pytest
from controleur_experimentation import Controleur
from proposeur_petites_regles import Projection, filtrer, proposer, regle
from test_controleur_experimentation import dossier
from test_propositions_python import deux_modeles

from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.langue import depuis_python, vers_python


def scene(x):
    def obj(pos, tag):
        return {"x": pos, "y": 0, "pixels": [[1]], "couche": 0, "tags": [tag], "nom": tag, "bloquant": True}

    return Scene((64, 64), 0, 0, [obj(0, "controle"), obj(x, "cible")])


@pytest.mark.parametrize("relation", ["contact_moteur", "proximite_boites"])
@pytest.mark.parametrize("effet", ["perdre", "gagner", "niveau_suivant"])
def test_grammaire_et_refutation(relation, effet):
    p = regle("controle", "cible", relation, effet)
    assert depuis_python(vers_python(p)) == p
    assert not filtrer(p, [([scene(0)], "continue")])["compatible"]
    assert filtrer(p, [([scene(9)], "continue")])["compatible"]


def test_intermediaire_contradictoire_non_ignore():
    p = regle("controle", "cible", "contact_moteur", "perdre")
    assert not filtrer(p, [([scene(9), scene(0), scene(9)], "continue")])["compatible"]


def test_projection_absorbante_et_entree_preservee():
    s = scene(0)
    p = Projection(lambda seq: [[s], [scene(9)]], regle("controle", "cible", "contact_moteur", "perdre"))
    assert p.simuler_seq(None, [["RIGHT"], ["LEFT"]])[0] == [("mort",), ("mort",)]
    assert s.issue is None


def test_pas_de_perception_pas_de_regle():
    d = dossier(deux_modeles())
    assert proposer(d, {}, None)["statut"] == "perception_ou_dynamique_non_admissible"


def test_raccord_ne_ferme_pas_couverture_et_ne_modifie_pas_base():
    cs = deux_modeles()
    d = dossier(cs)
    before = copy.deepcopy(cs["libre"].programme)
    signature = d.signature()
    r = Controleur().decider(d, cs, petites_regles=True)
    assert "issues" in r["incertitudes"] and not r["droit_action"]
    assert r["petites_regles"]["sdk"] == 0
    assert cs["libre"].programme == before and d.signature() == signature
