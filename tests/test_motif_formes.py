# SPDX-License-Identifier: MIT-0
"""C (ft09 N5, CCM-039-E) : le voisinage basculé dépend de la FORME de la tuile cliquée. Tuile simple (bloc 3×3) : elle
seule ; tuile croix (X de 14, « + » de 6) : elle et ses 4 voisines à un pas de tuile (4 cases)."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.theorie import Theorie, rejeu

CROIX = (6, 6)  # coin haut-gauche de la tuile croix ; tuiles simples à 4 cases autour, et une isolée en (14, 14)
SIMPLES = [(2, 6), (10, 6), (6, 2), (6, 10), (14, 14)]


def _grille(etat):
    g = np.zeros((20, 20), int)
    for (x, y), c in etat.items():
        if (x, y) == CROIX:
            for i in range(3):
                for j in range(3):
                    g[y + j, x + i] = c if (i + j) % 2 == 0 else 6
        else:
            g[y:y + 3, x:x + 3] = c
    return g


def _traj():
    etat = {t: 14 for t in [CROIX, *SIMPLES]}
    imgs, acts = [_grille(etat)], []
    for tuile in [(14, 14), CROIX, (2, 6), CROIX]:
        bas = [tuile] if tuile != CROIX else [CROIX, (2, 6), (10, 6), (6, 2), (6, 10)]
        for t in bas:
            etat[t] = 29 - etat[t]  # 14 ↔ 15
        acts.append(("clic", tuile[0] + 1, tuile[1] + 1))
        imgs.append(_grille(etat))
    return Trajectoire(imgs, [("clic", x, y) for _, x, y in acts], ech=(1, 0, 0))


def test_motif_selon_la_forme(monkeypatch):
    from chrysalide.arc3.logique.induction import induire
    monkeypatch.setenv("CHRYS_MOTIF_FORME", "1")
    tr = _traj()
    th = induire([(tr, None, None)], limite_s=20)[0]
    assert len(th.motif_formes) == 2
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_motif_selon_la_forme_exporte(monkeypatch):
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.logique.induction import induire
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    monkeypatch.setenv("CHRYS_MOTIF_FORME", "1")
    tr = _traj()
    th = induire([(tr, None, None)], limite_s=20)[0]
    prog, non = exporter(th, tr.taille)
    assert not non, non
    p, sc = Programme(prog), Scene((20, 20), 0, 0, [_sprite(o) | {"visible": True} for o in tr.etats[0]])
    k, o = 64 // 20, (64 - 60) // 2  # écran 64×64 : cases de 3 pixels, bordure de 2 (Programme._clic_vers_case)
    for a, g in zip(tr.actions, tr.cases[1:]):
        p.step(sc, ("MOUSE", o + a[2] * k + 1, o + a[1] * k + 1))
        assert (np.asarray(sc.image())[o::k, o::k][:20, :20] == np.asarray(g)).all()


def test_drapeau_eteint_rien_ne_change():
    assert Theorie().motif_formes == ()
