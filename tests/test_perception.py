import random

from chrysalide.arc3.perception import Routeur, appliquer, compacter, decompacter, diff


def grille_alea(graine, h=16, w=16):
    rnd = random.Random(graine)
    g = [[0] * w for _ in range(h)]
    for _ in range(8):
        c, r, k, hh, ww = rnd.randrange(1, 16), rnd.randrange(h), rnd.randrange(w), rnd.randrange(1, 5), rnd.randrange(1, 5)
        for i in range(r, min(h, r + hh)):
            for j in range(k, min(w, k + ww)):
                g[i][j] = c
    for _ in range(10):
        g[rnd.randrange(h)][rnd.randrange(w)] = rnd.randrange(16)
    return g


def test_compacte_sans_perte():
    for s in range(50):
        g = grille_alea(s)
        assert decompacter(compacter(g)) == g


def test_rectangle_sans_masque_et_forme_avec_masque():
    g = [[0] * 6 for _ in range(6)]
    for i in range(1, 3):
        for j in range(1, 4):
            g[i][j] = 2
    g[4][0] = g[5][0] = g[5][1] = 7
    t = compacter(g).split("\n")
    assert t[0] == "fond 0 6x6"
    assert "2 1,1 2x3" in t
    assert "7 4,0 2x2 #./##" in t


def test_diff_puis_appliquer_reconstruit():
    for s in range(30):
        a, b = compacter(grille_alea(s)), compacter(grille_alea(s + 100))
        assert appliquer(a, diff(a, b)) == b
    a = compacter(grille_alea(1))
    assert diff(a, a) == ""


def test_routeur_haute_puis_compacte_puis_retour():
    r = Routeur(calme=2, stagnation=3)
    assert r.tour(1) == ("haute", "debut")
    assert r.tour(1)[0] == "haute"
    assert r.tour(1)[0] == "compacte"
    assert r.tour(1, surprise=True) == ("haute", "surprise")
    r.tour(1), r.tour(1)
    assert r.tour(2) == ("haute", "niveau")
    r.tour(2), r.tour(2)
    assert r.tour(2, etat_neuf=False)[0] == "compacte"
    r.tour(2, etat_neuf=False)
    assert r.tour(2, etat_neuf=False) == ("haute", "stagnation")
