"""D (CW-239) : objets de même couleur et forme qui réagissent différemment à la même action → classes distinctes ;
aucun conflit → états inchangés (F-C2) ; image nouvelle → classes héritées par appariement."""
from chrysalide.arc3.logique.faits import comportements, couleur_vraie, heriter_classes

UN = frozenset({(0, 0)})


def _miroir():
    # flèche droite (4) : l'objet de gauche va à droite, celui de droite à gauche (m0r0)
    e0 = ((10, UN, 3, 5), (10, UN, 7, 5))
    e1 = ((10, UN, 4, 5), (10, UN, 6, 5))
    e2 = ((10, UN, 3, 5), (10, UN, 7, 5))
    return [e0, e1, e2], [4, 3]


def test_miroir_separe():
    etats, actions = _miroir()
    out, carte = comportements(etats, actions)
    assert len({o[0] for o in out[0]}) == 2 and {couleur_vraie(o[0]) for o in out[0]} == {10}
    assert carte


def test_sans_conflit_inchange():
    e0 = ((10, UN, 3, 5), (10, UN, 7, 5))
    e1 = ((10, UN, 4, 5), (10, UN, 8, 5))  # les deux vont dans le même sens
    out, carte = comportements([e0, e1], [4])
    assert out == [e0, e1] and carte == {}


def test_atomes_exclus():
    etats, actions = _miroir()
    out, carte = comportements(etats, actions, sauf=frozenset({10}))
    assert out == etats and carte == {}


def test_image_nouvelle_herite():
    etats, actions = _miroir()
    out, carte = comportements(etats, actions)
    nouvelle = ((10, UN, 3, 6), (10, UN, 7, 6))
    h = heriter_classes(etats[-1], carte, nouvelle)
    assert sorted(o[0] for o in h) == sorted(o[0] for o in out[-1])


def test_identite_persiste_quand_la_couleur_change():
    """CW-249 (3) : un interrupteur qui passe de 5 à 15 au même endroit garde son identité ; le changement est noté."""
    from chrysalide.arc3.logique.faits import identites
    e0 = ((2, UN, 1, 1), (5, UN, 4, 4))
    e1 = ((2, UN, 2, 1), (15, UN, 4, 4))
    ids, chg = identites([e0, e1])
    i5, i15 = e0.index((5, UN, 4, 4)), e1.index((15, UN, 4, 4))
    assert ids[1][i15] == ids[0][i5]
    assert chg == [(0, ids[0][i5], (5, UN), (15, UN))]


def test_identite_rotation_et_loin_nouvel_objet():
    from chrysalide.arc3.logique.faits import identites
    barre_h, barre_v = frozenset({(0, 0), (1, 0), (2, 0)}), frozenset({(0, 0), (0, 1), (0, 2)})
    e0 = ((3, barre_h, 4, 4),)
    e1 = ((3, barre_v, 5, 3),)        # même centre ou presque : rotation, même objet
    e2 = ((3, barre_v, 5, 3), (9, UN, 20, 20))  # un objet lointain est nouveau
    ids, chg = identites([e0, e1, e2])
    assert ids[1][0] == ids[0][0] and len(chg) == 1
    assert ids[2][e2.index((9, UN, 20, 20))] not in (ids[0][0],)
