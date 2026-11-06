from accessibilite_contact import resume_trajet, trajet


def test_contact_transitoire_ne_devient_pas_action_accessible():
    r = resume_trajet([[False, False], [True, False], [True, True]])
    assert r["passages_separateurs"] == [1] and not r["separation_fin"]
    assert r["issues"] == ["defaite", "defaite"]


def test_action_finissant_dans_bande_est_separatrice():
    assert resume_trajet([[False, False], [True, False]])["separation_fin"]


def test_effet_terminal_non_annule_par_sortie_du_contact():
    r = resume_trajet([[True, False], [False, False]])
    assert r["issues"] == ["defaite", "continue"]


def test_trajet_horizontal_puis_gravite_sans_teleportation():
    assert list(trajet((1, 1), (2, 0), 2)) == [((3, 2), "droite"), ((4, 2), "droite"), ((4, 1), "haut"), ((4, 0), "haut")]
