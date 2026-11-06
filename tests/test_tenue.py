# SPDX-License-Identifier: MIT-0
"""C (g50t : dalle → porte) : la porte disparaît tant qu'un mobile est sur la dalle, et revient quand il la quitte."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import trouver_tenue
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _traj():
    imgs, acts = [], []
    for k, x in enumerate((0, 1, 2, 3, 2, 1)):  # le joueur (3) passe sur la dalle (6, en x = 2), la quitte, y revient
        g = np.zeros((8, 8), int)
        g[1, 2] = 6
        g[1, x] = 3              # le joueur cache la dalle quand il est dessus
        if x != 2:
            g[4, 6] = 7          # porte (7) présente sauf quand la dalle est occupée (loin du bord : pas une jauge)
        imgs.append(g)
        if k:
            acts.append(4 if x > (0, 1, 2, 3, 2, 1)[k - 1] else 3)
    return Trajectoire(imgs, acts, ech=(1, 0, 0))


def test_porte_tenue_par_la_dalle():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(tr, None, None)])
    assert th.tenue == ((7, 6),) and "tenue(c7,c6)." in th.texte()
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_tenue_exportee():
    """Programme exporté : la porte est cachée quand le joueur est sur la dalle, montrée sinon."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    un = frozenset({(0, 0)})
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)}, tenue=((7, 6),))
    prog, non = exporter(th, (8, 8))
    assert not non
    sc = Scene((8, 8), 0, 0, [_sprite(o) | {"visible": True} for o in ((6, un, 2, 1), (7, un, 6, 4), (3, un, 1, 1))])
    vus = []
    for nom in ("RIGHT", "RIGHT", "LEFT"):
        Programme(prog).step(sc, (nom,))
        vus.append(next(s.get("visible", True) for s in sc.sprites if int(np.asarray(s["pixels"]).max()) == 7))
    assert vus == [False, True, False]


def test_porte_qui_pivote():
    """g50t (CCM-021-G) : la porte fait partie d'un objet plus grand et CHANGE de forme quand la dalle est occupée."""
    xs = (0, 1, 2, 3, 2, 1)
    imgs, acts = [], []
    for k, x in enumerate(xs):
        g = np.zeros((8, 8), int)
        g[1, 2] = 6               # dalle
        g[4, 4:7] = 7             # fil, toujours là
        if x == 2:
            g[5, 6] = g[6, 6] = 7  # porte ouverte : elle pivote vers le bas
        else:
            g[4, 7] = 7            # porte fermée : prolonge le fil
        g[1, x] = 3
        imgs.append(g)
        if k:
            acts.append(4 if x > xs[k - 1] else 3)
    tr = Trajectoire(imgs, acts, ech=(1, 0, 0))
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(tr, None, None)])
    assert [(p, len(r), len(a)) for p, r, a, _ in th.tenue_cases] == [(7, 1, 2)]
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_porte_qui_pivote_exportee():
    """Programme exporté : la porte pivotante (cases hors du cadre de l'objet d'origine) redonne les images, coup après coup."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    xs = (0, 1, 2, 3, 2, 1)
    imgs = []
    for x in xs:
        g = np.zeros((8, 8), int)
        g[1, 2] = 6
        g[4, 4:7] = 7
        if x == 2:
            g[5, 6] = g[6, 6] = 7
        else:
            g[4, 7] = 7
        g[1, x] = 3
        imgs.append(g)
    acts = [4 if x > xs[k] else 3 for k, x in enumerate(xs[1:])]
    tr = Trajectoire(imgs, acts, ech=(1, 0, 0))
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(tr, None, None)])
    prog, non = exporter(th, (8, 8))
    assert not non
    sps = [_sprite(o) | {"visible": True} | ({"couche": 1} if o[0] == 3 else {}) for o in tr.etats[0]]  # joueur sur la dalle
    p, sc = Programme(prog), Scene((8, 8), 0, 0, sps)
    for a, g in zip(acts, imgs[1:]):
        p.step(sc, ({4: "RIGHT", 3: "LEFT"}[a],))
        assert (np.asarray(sc.image())[::8, ::8] == g).all()


def test_porte_vue_dans_la_seconde_trajectoire():
    """CCM-021-G : la porte n'est vue que dans les coups-expériences (2ᵉ trajectoire) ; la 1ʳᵉ ne la contredit pas."""
    def traj(xs):
        imgs = []
        for x in xs:
            g = np.zeros((8, 8), int)
            g[1, 2] = 6
            g[4, 4:7] = 7
            if x == 2:
                g[5, 6] = g[6, 6] = 7
            else:
                g[4, 7] = 7
            g[1, x] = 3
            imgs.append(g)
        return Trajectoire(imgs, [4 if x > xs[k] else 3 for k, x in enumerate(xs[1:])], ech=(1, 0, 0))
    th = Theorie(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(traj((0, 1, 0, 1)), None, None), (traj((0, 1, 2, 3, 2, 1)), None, None)])
    assert [(p, len(r), len(a)) for p, r, a, _ in th.tenue_cases] == [(7, 1, 2)]


def test_porte_pivotante_est_un_mur():
    """g50t : les cases retirées à l'ouverture qui deviennent le sol d'une autre classe sont une porte : elles bloquent."""
    from chrysalide.arc3.logique.theorie import Theorie as T
    th = T(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    xs = (0, 1, 2, 3, 2, 1)
    imgs = []
    for x in xs:
        g = np.zeros((8, 8), int)
        g[1, 2] = 6
        g[4, 4:7] = 7
        g[5, 6] = 5 if x == 2 else 7   # porte (7) qui laisse place au sol (5) quand la dalle est occupée
        g[6, 6] = 5
        if x == 2:
            g[4, 7] = 5
        g[1, x] = 3
        imgs.append(g)
    acts = [4 if x > xs[k] else 3 for k, x in enumerate(xs[1:])]
    trouver_tenue(th, [(Trajectoire(imgs, acts, ech=(1, 0, 0)), None, None)])
    assert (7, frozenset({(6, 5)})) in th.portes_cases and 7 not in th.solides  # la case de porte, pas tout le fil


def _niveau(dx, dy, xs, couleurs=(6, 7, 5, 3)):
    """Dalle (d) et porte pivotante (p) sur un sol (s), décalées de (dx, dy) ; le joueur (j) suit xs sur la ligne de la
    dalle. Porte fermée : prolonge le fil ; ouverte (joueur sur la dalle) : pivote vers le bas."""
    d, p, s, j = couleurs
    imgs = []
    for x in xs:
        g = np.zeros((14, 14), int)
        g[1 + dy, dx:dx + 4] = s
        g[1 + dy, 2 + dx] = d
        g[4 + dy, 4 + dx:7 + dx] = p
        if x == 2:
            g[5 + dy, 6 + dx] = g[6 + dy, 6 + dx] = p
        else:
            g[4 + dy, 7 + dx] = p
        g[1 + dy, x + dx] = j
        imgs.append(g)
    return imgs


def test_porte_relative_suit_la_translation(monkeypatch):
    """CW-350 (test de translation) : la loi vue au niveau 1 est reconnue au niveau 2, décalé de (5, 6), par ses motifs."""
    from chrysalide.arc3.logique.theorie import Theorie as T
    monkeypatch.setenv("CHRYS_PORTE_RELATIVE", "1")
    xs = (0, 1, 2, 3, 2, 1)
    t1 = Trajectoire(_niveau(0, 0, xs), [4 if x > xs[k] else 3 for k, x in enumerate(xs[1:])], ech=(1, 0, 0))
    t2 = Trajectoire(_niveau(5, 6, (0,)), [], ech=(1, 0, 0))
    t1.niveau, t2.niveau = 1, 2
    th = T(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(t1, None, None), (t2, None, None)])
    loi = [x for x in th.tenue_cases if x[0] == 7]
    assert loi and loi[0][1] == frozenset({(12, 10)}) and loi[0][2] == frozenset({(11, 11), (11, 12)})
    assert (7, 7) in loi[0][3]  # la dalle du niveau 2


def test_porte_relative_sans_nom(monkeypatch):
    """CW-350 (test de permutation) : mêmes niveaux, identifiants de classe permutés partout → même loi, classes renommées."""
    from chrysalide.arc3.logique.theorie import Theorie as T
    monkeypatch.setenv("CHRYS_PORTE_RELATIVE", "1")
    xs = (0, 1, 2, 3, 2, 1)
    c = (11, 12, 13, 3)
    t1 = Trajectoire(_niveau(0, 0, xs, c), [4 if x > xs[k] else 3 for k, x in enumerate(xs[1:])], ech=(1, 0, 0))
    t2 = Trajectoire(_niveau(5, 6, (0,), c), [], ech=(1, 0, 0))
    t1.niveau, t2.niveau = 1, 2
    th = T(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(t1, None, None), (t2, None, None)])
    loi = [x for x in th.tenue_cases if x[0] == 12]
    assert loi and loi[0][1] == frozenset({(12, 10)}) and loi[0][2] == frozenset({(11, 11), (11, 12)})


def test_porte_relative_eteinte_ou_ambigue(monkeypatch):
    """Drapeau éteint : rien n'est transféré. Deux portes identiques au niveau 2 : liaison ambiguë → abstention."""
    from chrysalide.arc3.logique.theorie import Theorie as T
    xs = (0, 1, 2, 3, 2, 1)
    t1 = Trajectoire(_niveau(0, 0, xs), [4 if x > xs[k] else 3 for k, x in enumerate(xs[1:])], ech=(1, 0, 0))
    t2 = Trajectoire(_niveau(5, 6, (0,)), [], ech=(1, 0, 0))
    t1.niveau, t2.niveau = 1, 2
    th = T(moves={(3, 4): (1, 0), (3, 3): (-1, 0)})
    trouver_tenue(th, [(t1, None, None), (t2, None, None)])
    assert th.tenue_cases == ()
