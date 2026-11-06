# SPDX-License-Identifier: MIT-0
"""C (g50t N1) : sous SPACE, le joueur revient à sa position de départ (loi « retour », CHRYS_RETOUR)."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import trouver_retour
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _traj():
    xs, acts = [1], []
    for a in (4, 4, 5, 4, 5, 4, 4, 5):  # RIGHT avance d'une case, SPACE ramène en x = 1
        xs.append(1 if a == 5 else xs[-1] + 1)
        acts.append(a)
    imgs = []
    for x in xs:
        g = np.zeros((5, 8), int)
        g[2, x] = 3
        imgs.append(g)
    return Trajectoire(imgs, acts, ech=(1, 0, 0))


def test_retour_au_depart():
    tr = _traj()
    th = Theorie(moves={(3, 4): (1, 0), (3, 5): (-1, 0)})  # pas inventé sous SPACE
    trouver_retour(th, [(tr, None, None)])
    assert th.retour == ((3, 5, 1, 2),) and (3, 5) not in th.moves and "retour(c3,a5,1,2)." in th.texte()
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_fantome_rejoue_le_trajet():
    """Boucle temporelle (g50t) : SPACE ramène le joueur au départ ; le fantôme rejoue ses pas effectifs, un par coup ;
    au SPACE suivant (emplacement plein) il s'efface sans être remplacé."""
    un = frozenset({(0, 0)})
    th = Theorie(moves={(3, 4): (1, 0), (3, 2): (0, 1)}, retour=((3, 5, 0, 0),), fantome=(3, 5, 2, 0, 0))
    m = ((3, un, 0, 0),)
    for a in (4, 4, 5):  # deux pas à droite, puis boucle
        m, _ = th.pas(m, a, (8, 8))
    pos = []
    for a in (2, 2, 2):  # le joueur descend ; le fantôme rejoue : (1, 0), (2, 0), puis reste
        m, _ = th.pas(m, a, (8, 8))
        pos.append([(o[2], o[3]) for o in m if o[0] == 2])
    assert pos == [[(1, 0)], [(2, 0)], [(2, 0)]]
    m, _ = th.pas(m, 5, (8, 8))  # emplacement plein : effacé, pas de nouveau fantôme
    assert not [o for o in m if o[0] == 2]


def test_boucle_sans_trajet_ne_fait_rien():
    """g50t (films) : SPACE sans pas enregistré ne crée ni n'efface de fantôme."""
    un = frozenset({(0, 0)})
    th = Theorie(moves={(3, 4): (1, 0)}, retour=((3, 5, 0, 0),), fantome=(3, 5, 2, 0, 0))
    m = ((3, un, 0, 0),)
    m, _ = th.pas(m, 4, (8, 8))
    m, _ = th.pas(m, 5, (8, 8))   # boucle : fantôme créé (trajet d'un pas)
    m, _ = th.pas(m, 5, (8, 8))   # boucle à vide (aucun pas depuis) : rien ne change
    m, _ = th.pas(m, 4, (8, 8))   # le fantôme rejoue son pas
    assert [(o[2], o[3]) for o in m if o[0] == 2] == [(1, 0)]


def test_retour_exporte():
    """La loi `retour` passe dans le langage : sous SPACE, l'objet est replacé au départ."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    th = Theorie(moves={(3, 4): (1, 0)}, retour=((3, 5, 1, 2),))
    prog, non = exporter(th, (8, 5))
    assert not non
    sc = Scene((5, 8), 0, 0, [_sprite((3, frozenset({(0, 0)}), 4, 2)) | {"visible": True}])
    Programme(prog).step(sc, ("SPACE",))
    assert [(s["x"], s["y"]) for s in sc.sprites] == [(1, 2)]


def test_fantome_exporte():
    """Le programme exporté reproduit la boucle temporelle de la théorie : mêmes positions du fantôme, coup après coup."""
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    un = frozenset({(0, 0)})
    th = Theorie(moves={(3, 4): (1, 0), (3, 2): (0, 1)}, retour=((3, 5, 0, 0),), fantome=(3, 5, 2, 0, 0))
    prog, non = exporter(th, (8, 8))
    assert not non
    p, sc = Programme(prog), Scene((8, 8), 0, 0, [_sprite((3, un, 0, 0)) | {"visible": True}])
    m, vus_t, vus_p = ((3, un, 0, 0),), [], []
    for a, nom in ((4, "RIGHT"), (4, "RIGHT"), (5, "SPACE"), (2, "DOWN"), (2, "DOWN"), (2, "DOWN"), (5, "SPACE")):
        m, _ = th.pas(m, a, (8, 8))
        p.step(sc, (nom,))
        vus_t.append(sorted((o[0], o[2], o[3]) for o in m if o[0] < 1024))
        vus_p.append(sorted((int(np.asarray(s["pixels"]).max()), s["x"], s["y"]) for s in sc.sprites if s.get("visible", True)))
    assert vus_p == vus_t


def test_depart_du_niveau_courant():
    """CCM-219-C : avec des trajectoires marquées de niveaux différents, le départ (retour, fantôme) est celui de la 1re
    image du niveau courant (la dernière trajectoire) ; sans marque, inchangé."""
    from types import SimpleNamespace

    from chrysalide.arc3.logique.induction import _au_depart_courant
    un = frozenset({(0, 0)})
    t1 = SimpleNamespace(etats=[((3, un, 1, 1),)], niveau=1)
    t2 = SimpleNamespace(etats=[((3, un, 5, 6),)], niveau=2)
    assert _au_depart_courant([(3, 5, 1, 1)], [(t1,), (t2,)]) == [(3, 5, 5, 6)]
    assert _au_depart_courant([(3, 5, 2, 7, 1, 1)], [(t1,), (t2,)]) == [(3, 5, 2, 7, 5, 6)]
    t2.niveau = 1
    assert _au_depart_courant([(3, 5, 1, 1)], [(t1,), (t2,)]) == [(3, 5, 1, 1)]
