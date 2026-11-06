import json

import pytest
from hypotheses_navigation import HypothesesNavigation
from transfert_navigation_bp35 import apprendre


def test_selection_depuis_films_N1_sans_solution_N2():
    m, h, buts, _z, _j = apprendre()
    assert h.actives() == ["g-1_clic1"]
    assert buts and not buts & m.palette
    assert len(h.journal) == 14
    assert all(r["frames"] > 1 for r in h.journal)


def test_reouverture_parametre_local_sans_forcer_N1():
    m, _h, buts, _z, _j = apprendre()
    nxt = HypothesesNavigation(m, buts, clics=(True,))
    assert len(nxt.actives()) == 3
    assert "g1_clic1" in nxt.actives()
    assert all(n.endswith("clic1") for n in nxt.actives())


def test_experience_et_prediction_ne_valident_pas_regle():
    m, _h, buts, z, _j = apprendre()
    nxt = HypothesesNavigation(m, buts, clics=(True,))
    p = nxt.proposer(z["images"][0], [3, 4, 6])
    assert p["experiences_candidates"] and p["gain_minimax"] > 0
    assert len(nxt.actives()) == 3
    json.dumps(p, default=int)


def test_gravite_nulle_termine_et_garde_hauteur():
    m, _h, buts, z, _j = apprendre()
    p = m.proposer(z["images"][0], gravite=0, buts_connus=buts)
    assert p["position_suivante_locale"][1] == p["position"][1]


def test_refutation_revoque_descendants_atms():
    m, _h, buts, z, j = apprendre()
    nxt = HypothesesNavigation(m, buts, clics=(True,))
    nxt.atms.justifier("plan", ["g1_clic1"])
    assert nxt.atms.tient("plan", ["g1_clic1"])
    nxt.observer(z["images"][0], j["actions"][0], z["images"][1], z["film_1"])
    assert not nxt.atms.tient("plan", ["g1_clic1"])


def test_catalogue_refute_ne_joue_pas():
    _m, h, _buts, z, _j = apprendre()
    for name in h.actives():
        h.atms.interdire([name])
    with pytest.raises(ValueError, match="Catalogue réfuté"):
        h.proposer(z["images"][0], [3, 4, 6])


def test_motif_connexe_resiste_aux_couleurs_partagees():
    from perception_navigation import position

    m, _h, _b, z, _j = apprendre()
    g = z["images"][0].copy()
    for i, c in enumerate(sorted(m.palette)):
        g[55, 3 + i] = c
    with pytest.raises(ValueError, match="Silhouette ambiguë"):
        m.position(g)
    assert position(m, g) == m.position(z["images"][0])


def test_double_motif_refuse_sans_inventer_identite():
    from perception_navigation import position

    m, _h, _b, z, _j = apprendre()
    g = z["images"][0].copy()
    g[49:53, 20:23] = g[37:41, 20:23]
    with pytest.raises(ValueError, match="non unique"):
        position(m, g)
