# SPDX-License-Identifier: MIT-0
"""C (ar25 N4, CHRYS_FORMES_SEL) : deux pièces de MÊME couleur, de formes différentes, jamais déplacées au même coup
(sélection) reçoivent chacune leur classe ; une marque qui suit la pièce choisie (quelle qu'elle soit) est un suiveur ;
un SPACE joué avant tout déplacement compte dans l'index initial de la sélection."""
import numpy as np

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import trouver_selection
from chrysalide.arc3.logique.theorie import Theorie, rejeu


def _traj():
    """L (3 cases) et barre (3 cases), couleur 5 ; SPACE au coup 0 choisit le L ; la marque (ligne 0) avance d'une case à
    chaque pas à droite de la pièce choisie, quelle qu'elle soit, et ne bouge pas sous SPACE."""
    imgs, acts = [], []
    u, b, m, sel = [2, 6], [8, 9], 3, None
    plan = [5, 4, 4, 5, 4, 1, 1]
    for k in range(len(plan) + 1):
        g = np.zeros((14, 14), int)
        g[u[1], u[0]] = g[u[1] + 1, u[0]] = g[u[1] + 1, u[0] + 1] = 5
        g[b[1]:b[1] + 3, b[0]] = 5
        g[0, m] = 4
        imgs.append(g)
        if k == len(plan):
            break
        a = plan[k]
        acts.append(a)
        if a == 5:
            sel = "u" if sel is None else ("b" if sel == "u" else "u")
            continue
        p = u if sel == "u" else b
        if a == 4:
            p[0] += 1
            m += 1
        elif a == 1:
            p[1] -= 1
    return Trajectoire(imgs, acts, ech=(1, 0, 0))


def test_pieces_de_meme_couleur_separees(monkeypatch):
    monkeypatch.setenv("CHRYS_FORMES_SEL", "1")
    tr = _traj()
    assert len({o[0] for o in tr.etats[0] if o[0] % 16 == 5}) == 2


def test_selection_avec_suiveur_et_index_initial(monkeypatch):
    monkeypatch.setenv("CHRYS_FORMES_SEL", "1")
    tr = _traj()
    th = Theorie()
    trouver_selection(th, [(tr, None, None)])
    assert th.selection and th.selection[0] == 5 and len(th.selection[1]) == 2
    assert th.selection[2] == 1  # SPACE au coup 0 : l'index part de la dernière pièce
    assert (4, 4) in th.moves  # la marque suit la pièce choisie
    th.hors_jeu = tr.exclues
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_drapeau_eteint(monkeypatch):
    monkeypatch.setenv("CHRYS_FORMES_SEL", "0")
    tr = _traj()
    assert {o[0] for o in tr.etats[0] if o[0] % 16 == 5} == {5}


def test_table_de_formes_heritee():
    """CCM-221-C : une trajectoire sans coup (début d'un niveau) hérite de la table « forme → classe » d'un niveau vu."""
    g = np.zeros((14, 14), int)
    g[2, 2] = g[3, 2] = g[3, 3] = 5   # le L, immobile
    g[9:12, 8] = 5                    # la barre
    nu = Trajectoire([g], [], ech=(1, 0, 0))
    assert {o[0] for o in nu.etats[0]} == {5}
    her = Trajectoire([g], [], ech=(1, 0, 0), formes_heritees={(5, frozenset({(0, 0), (0, 1), (1, 1)})): 277})
    assert 277 in {o[0] for o in her.etats[0]}


def test_jumeau_immobile_separe(monkeypatch):
    """ka59 N4 (CCM-044-E) : deux objets c14 d'une case, l'un piloté par les flèches, l'autre jamais déplacé → deux
    classes (CHRYS_IMMOBILE) ; drapeau éteint : une seule classe."""
    xs = [2, 3, 4, 4, 3]  # le joueur va à droite, bute, revient
    imgs, acts = [], [4, 4, 4, 3]
    for x in xs:
        g = np.zeros((10, 10), int)
        g[2, 1:8] = 0
        g[2, 5] = 2          # mur
        g[2, x] = 14         # joueur
        g[7, 7] = 14         # jumeau immobile (cible)
        imgs.append(g)
    imgs[3][2, 4] = 14
    monkeypatch.setenv("CHRYS_IMMOBILE", "0")
    tr = Trajectoire(imgs, acts, ech=(1, 0, 0))
    assert {o[0] for o in tr.etats[0] if o[0] % 16 == 14} == {14}
    monkeypatch.setenv("CHRYS_IMMOBILE", "1")
    tr = Trajectoire(imgs, acts, ech=(1, 0, 0))
    assert len({o[0] for o in tr.etats[0] if o[0] % 16 == 14}) == 2
