from perception_marqueur_candidat import formes_visibles


def objets(x,y,forme):
    return ((2,forme,x,y),(2,frozenset({(0,0)}),8,8))


def test_identite_conservee_au_bord():
    f=frozenset({(0,0),(0,1),(0,2)})
    es=[objets(3,y,f) for y in (4,5,6)]
    coupe=frozenset({(0,0),(0,1)})
    es.append(objets(3,7,coupe))
    fm=formes_visibles(es,[1,1,1],(10,9),frozenset())
    assert fm[2,f]==fm[2,coupe]


def test_reduction_interieure_non_assimilee_au_bord():
    f=frozenset({(0,0),(0,1),(0,2)})
    coupe=frozenset({(0,0),(0,1)})
    es=[objets(3,y,f) for y in (1,2,3)]+[objets(3,4,coupe)]
    assert (2,coupe) not in formes_visibles(es,[1,1,1],(10,10),frozenset())


def test_pas_de_classe_mobile_sans_deux_translations():
    f=frozenset({(0,0),(0,1),(0,2)})
    assert not formes_visibles([objets(3,4,f),objets(3,5,f)],[1],(10,10),frozenset())
