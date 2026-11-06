"""Graphe des transitions (voie 2 b) et explorateur, sur un couloir jouet avec une case mortelle."""
from chrysalide.arc3.explorateur import Explorateur
from chrysalide.arc3.graphe import Graphe, candidats, cle, decle, etat


def grille(pos):
    g = [[0] * 64 for _ in range(64)]
    g[10][10 + pos] = 3
    return g


def test_cle_aller_retour():
    assert decle(cle(6, 12, 40)) == (6, 12, 40) and decle(cle(4)) == (4, None, None)


def test_etat_ignore_la_bordure():
    g = grille(0)
    g2 = [r[:] for r in g]
    g2[0][5] = 9  # barre de vie en bordure
    assert etat(g) == etat(g2) and etat(g) != etat(grille(1)) and etat(g, 0) != etat(g, 1)


def test_candidats_clic_par_objet():
    g = grille(0)
    assert candidats(g, [1, 6]) == ["1", "6@10,10"]


def test_bfs_frontiere_evite_les_morts():
    G, s = Graphe(), [etat(grille(i)) for i in range(4)]
    for i in range(4):
        G.voir(s[i], ["3", "4"])
    G.noter(s[0], "4", s[1])
    G.noter(s[0], "3", s[0])  # sans effet
    G.noter(s[1], "3", s[0])
    G.noter(s[1], "4", s[2])
    G.noter(s[2], "4", s[3], mort=True)
    G.noter(s[2], "3", s[1])
    assert G.frontier_path(s[0]) is None  # seule frontière (s3) derrière une arête mortelle
    assert G.replay_to(s[0], s[2]) == ["4", "4"]
    assert G.replay_to(s[0], s[3]) is None and G.is_known_dead(s[2], "4")  # la route mortelle n'est jamais proposée
    assert G.prevision(s[1], "4") == s[2]


def test_explorateur_route_apres_mort():
    """Couloir : DROITE avance, à la 3e case on meurt ; après la mort, le graphe ramène à la frontière sans « nouveau »."""
    ex, pos, sources = Explorateur("graphe", 0), 0, []
    for _ in range(30):
        k, src, s0 = ex.choisir(grille(pos), 0, [3, 4])
        sources.append(src)
        mort = False
        if k == "4":
            pos += 1
            if pos == 3:
                mort, pos = True, 0
        elif k == "3":
            pos = max(0, pos - 1)
        ex.apprendre(s0, k, grille(pos if not mort else 0), 0, mort)
    assert "route" in sources and ex.g.is_known_dead(etat(grille(2)), "4")


def test_retour_rejoue_jusqu_avant_le_coup_fatal():
    """Après la mort en 3, « retour » rejoue 4,4 (sans modèle) jusqu'à la case 2, puis rend la main (coup « nouveau »)."""
    ex, pos, journal = Explorateur("retour", 0), 0, []
    ex.rng.choice = lambda xs: "4" if "4" in xs else xs[0]  # politique déterministe : toujours DROITE si non testé
    for _ in range(6):
        k, src, s0 = ex.choisir(grille(pos), 0, [3, 4])
        journal.append(src)
        mort = k == "4" and pos == 2
        pos = 0 if mort else (pos + 1 if k == "4" else max(0, pos - 1))
        ex.apprendre(s0, k, grille(pos), 0, mort)
    assert journal[:5] == ["nouveau", "nouveau", "nouveau", "route", "route"] and journal[5] == "nouveau"
