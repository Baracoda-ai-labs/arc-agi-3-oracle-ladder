"""D (CCM-080-C) : une couleur a une forme qui bouge et une autre jamais → la forme mobile a sa propre classe ; une bascule
de couleur (le nombre d'objets de la classe change) n'est pas un déplacement."""
from chrysalide.arc3.logique.faits import couleur_vraie, formes_mobiles, reclasser_formes

UN, DEUX = frozenset({(0, 0)}), frozenset({(0, 0), (1, 0)})


def test_forme_mobile_reclassee():
    e0 = ((3, UN, 1, 1), (3, DEUX, 5, 5))
    e1 = ((3, UN, 2, 1), (3, DEUX, 5, 5))
    e2 = ((3, UN, 3, 1), (3, DEUX, 5, 5))
    assert formes_mobiles([e0, e1]) == {}  # un seul déplacement : pas assez (CW-240)
    fm = formes_mobiles([e0, e1, e2])
    assert set(fm) == {(3, UN)}
    r = reclasser_formes(e1, fm)
    assert {o[0] for o in r if o[1] == UN} == {fm[(3, UN)]} and couleur_vraie(fm[(3, UN)]) == 3
    assert any(o[0] == 3 and o[1] == DEUX for o in r)


def test_bascule_n_est_pas_un_deplacement():
    e0 = ((3, UN, 1, 1), (3, UN, 2, 1), (3, DEUX, 5, 5))
    e1 = ((3, UN, 2, 1), (3, DEUX, 5, 5), (4, UN, 1, 1))  # la case (1,1) passe de 3 à 4 : rien n'a bougé
    assert formes_mobiles([e0, e1]) == {}


def test_codes_stables_quand_on_ajoute_des_images():
    """CCM-089-C (réserve 1) : une forme mobile nouvelle ne décale pas le code des formes déjà vues."""
    trois = frozenset({(0, 0), (1, 0), (2, 0)})
    e0 = ((3, DEUX, 1, 1), (3, UN, 8, 8), (3, trois, 5, 5))
    e1 = ((3, DEUX, 2, 1), (3, UN, 8, 8), (3, trois, 5, 5))
    e2 = ((3, DEUX, 3, 1), (3, UN, 8, 8), (3, trois, 5, 5))
    e3 = ((3, DEUX, 3, 1), (3, UN, 8, 9), (3, trois, 5, 5))  # la petite forme (triée avant) ne bouge qu'ensuite
    e4 = ((3, DEUX, 3, 1), (3, UN, 8, 10), (3, trois, 5, 5))
    avant, apres = formes_mobiles([e0, e1, e2]), formes_mobiles([e0, e1, e2, e3, e4])
    assert avant[(3, DEUX)] == apres[(3, DEUX)] and (3, UN) in apres


def test_forme_qui_change_n_est_pas_reclassee():
    """CW-240 (ar25) : une forme absente d'une image (reflet, occultation) n'est pas reclassée."""
    e0 = ((3, UN, 1, 1), (3, DEUX, 5, 5))
    e1 = ((3, UN, 2, 1), (3, DEUX, 5, 5))
    e2 = ((3, DEUX, 3, 1), (3, DEUX, 5, 5))  # la forme mobile a changé
    e3 = ((3, UN, 4, 1), (3, DEUX, 5, 5))
    assert (3, UN) not in formes_mobiles([e0, e1, e2, e3])
