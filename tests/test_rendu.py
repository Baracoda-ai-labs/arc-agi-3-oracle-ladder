"""Rendu inverse (CW-062.2) : cas propre fabriqué (vue 16×16 ×4, letterbox, HUD) et suivi des sprites d'un coup à l'autre."""
import numpy as np

from chrysalide.arc3.rendu import peindre, rendu, suivre


def image(px, py, hud=True):
    vue = np.zeros((14, 14), dtype=int)
    vue[py, px] = 3
    vue[py, px + 1] = 7  # sprite à deux couleurs qui bouge d'un bloc
    vue[10:12, 2:5] = 5  # mur fixe
    g = np.full((64, 64), 9)
    k, y0 = 4, (64 - 14 * 4) // 2
    g[y0:y0 + 56, y0:y0 + 56] = np.repeat(np.repeat(vue, k, 0), k, 1)
    if hud:
        g[0, :20] = 2  # barre de budget dessinée par-dessus, en résolution 64
    return g


def test_cas_propre_echelle_cadre_sans_perte():
    g = image(3, 4)
    r = rendu(g)
    assert r["echelle"] == 4 and r["cadre"] == (4, 4, 56, 56) and r["grille"].shape == (14, 14)
    assert (peindre(r) == g).all() and len(r["hud"]) == 20
    assert {s[1] for s in r["sprites"]} == {3, 5, 7}


def test_suivre_regroupe_les_sprites_qui_bougent_ensemble():
    r0, r1 = rendu(image(3, 4)), rendu(image(4, 4))
    s = suivre(r0, r1)
    assert sorted(c for c in s["objets"][0]) == sorted(c for c in s["objets"][0]) and len(s["objets"]) == 1
    assert {c for _, c in s["objets"][0]} == {3, 7} and not s["nouveaux"] and not s["disparus"]


def test_pisteur_recolle_un_sprite_bicolore_qui_bouge():
    from chrysalide.arc3.objets_temps import Pisteur
    p = Pisteur()
    g = np.zeros((16, 16), dtype=int)
    g[5, 3], g[5, 4], g[10, 10] = 3, 7, 5
    o0 = p.observer(g)
    assert len(o0) == 3  # avant tout mouvement : 3 composantes
    g2 = np.zeros((16, 16), dtype=int)
    g2[5, 4], g2[5, 5], g2[10, 10] = 3, 7, 5
    o1 = p.observer(g2)
    assert len(o1) == 2 and {(5, 4), (5, 5)} in [set(v) for v in o1.values()]  # le bicolore est un seul objet


def test_pisteur_defait_une_union_quand_les_morceaux_se_separent():
    from chrysalide.arc3.objets_temps import Pisteur
    p = Pisteur()

    def img(a, b):
        g = np.zeros((16, 16), dtype=int)
        g[5, a], g[5, b] = 3, 7
        return g
    p.observer(img(3, 4))
    assert len(p.observer(img(4, 5))) == 1      # bougent ensemble, contigus : un objet
    assert len(p.observer(img(3, 6))) == 2      # se séparent (déplacements opposés, miroir) : deux objets
    q = Pisteur(revisable=False)
    q.observer(img(3, 4))
    q.observer(img(4, 5))
    assert len(q.observer(img(3, 6))) == 1      # version définitive : reste fusionné (défaut vu sur ar25)


def test_rendre_comme_arcengine():
    from chrysalide.arc3.ontologie_exec import rendre
    scene = {"vue": (8, 8), "fond": 0, "letterbox": 5, "camera": (0, 0),
             "sprites": [{"pixels": [[3, 3], [3, -1]], "x": 1, "y": 1, "couche": 0},
                         {"pixels": [[7]], "x": 2, "y": 2, "couche": -1}]}   # calque inférieur, sous un pixel transparent
    g = rendre(scene)
    assert g.shape == (64, 64) and (g[8:16, 8:16] == 3).all() and g[16, 16] == 7 and g[0, 0] == 0


def test_scene_retirer_par_identite():
    from chrysalide.arc3.ontologie_exec import Scene
    s = {"pixels": [[1]], "x": 0, "y": 0, "couche": 0}
    sc = Scene((4, 4), 0, 0, [s, dict(s)])   # deux sprites identiques en valeur
    sc.retirer(sc.sprites[1])
    assert len(sc.sprites) == 1
