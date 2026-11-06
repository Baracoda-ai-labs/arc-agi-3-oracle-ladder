# SPDX-License-Identifier: MIT-0
"""CW-224 : prédiction avec abstention — rien n'est accepté sans relation démontrée."""
from chrysalide.arc3.logique.prediction import Connaissance, predire
from chrysalide.arc3.logique.theorie import Theorie

F = frozenset({(0, 0)})


class Tr:
    def __init__(self, etats, actions, taille=(8, 3)):
        self.etats, self.actions, self.taille, self.exclues = etats, actions, taille, frozenset()


def _couloir():
    # mobile 1 va à droite deux fois sur le fond, un objet 2 est plus loin, jamais touché
    return Tr([((1, F, x, 1), (2, F, 5, 1)) for x in range(3)], [4, 4])


def test_deplacement_demontre_accepte():
    tr, th = _couloir(), Theorie(moves={(1, 4): (1, 0)})
    pred, raison = predire(th, Connaissance(tr, range(2)), tr.etats[2], 4, tr.taille)
    assert raison is None and (1, F, 3, 1) in pred


def test_mur_suppose_inconnu_abstention():
    tr = _couloir()
    th = Theorie(moves={(1, 4): (1, 0)}, solides=frozenset({2}), murs_supposes=frozenset({2}))
    monde = ((1, F, 4, 1), (2, F, 5, 1))  # le mobile vise l'objet 2 : passabilité jamais observée
    pred, raison = predire(th, Connaissance(tr, range(2)), monde, 4, tr.taille)
    assert pred is None and "passabilité inconnue" in raison


def test_action_jamais_vue_abstention():
    tr, th = _couloir(), Theorie(moves={(1, 4): (1, 0)})
    pred, _ = predire(th, Connaissance(tr, range(2)), tr.etats[2], 3, tr.taille)
    assert pred is None


def test_garder_coupe_avant_la_premiere_abstention():
    from chrysalide.arc3.logique.prediction import garder
    tr, th = _couloir(), Theorie(moves={(1, 4): (1, 0)})
    garde, raison = garder(th, tr, [4, 4, 4, 4], k=3)  # 3 → 4 sur le fond, puis l'objet 2 en (5, 1) : inconnu
    assert garde == [4, 4] and "passabilité inconnue" in raison


def test_moteur_garde_rend_le_plan_entier_et_la_longueur_gardee(monkeypatch):
    from types import SimpleNamespace

    from chrysalide.arc3.moteur import _garde
    tr, th, m = _couloir(), Theorie(moves={(1, 4): (1, 0)}), SimpleNamespace(infos={})
    monkeypatch.delenv("CHRYS_GARDE", raising=False)
    assert _garde(m, th, tr, [4, 4, 4, 4]) == [4, 4, 4, 4] and "garde_n" not in m.infos  # éteint : rien ne change
    monkeypatch.setenv("CHRYS_GARDE", "3")
    assert _garde(m, th, tr, [4, 4, 4, 4]) == [4, 4, 4, 4] and m.infos["garde_n"] == 2  # plan entier pour la porte 2
    assert _garde(m, th, tr, [3, 4]) == []  # 1er coup incertain (action jamais vue) : refus


def test_limite_invisible_deja_vue_abstention():
    # le mobile est entré sur le fond (x 0 → 1 → 2), puis est resté en x = 2 sous le même coup : limite invisible
    tr = Tr([((1, F, 0, 1),), ((1, F, 1, 1),), ((1, F, 2, 1),), ((1, F, 2, 1),)], [4, 4, 4])
    th = Theorie(moves={(1, 4): (1, 0)})
    conn = Connaissance(tr, range(3))
    assert conn.passabilite(1, "fond", (1, 0)) == "contradictoire"
    pred, raison = predire(th, conn, ((1, F, 2, 1),), 4, tr.taille)
    assert pred is None and "immobilité déjà vue ici" in raison
    pred, raison = predire(th, conn, ((1, F, 0, 1),), 4, tr.taille)  # ailleurs : le fond est « contradictoire »
    assert pred is None and "contradictoire" in raison


def test_rejeu_contrat_ignore_le_hors_contrat():
    from chrysalide.arc3.logique.prediction import rejeu_contrat
    # le mobile 1 avance comme prévu ; un objet 3 hors contrat change de place sans que la théorie le sache
    tr = Tr([((1, F, 0, 1), (3, F, 7, 0)), ((1, F, 1, 1), (3, F, 6, 0)), ((1, F, 2, 1), (3, F, 5, 0))], [4, 4])
    th = Theorie(moves={(1, 4): (1, 0)})
    assert rejeu_contrat(th, tr)[:2] == (2, 2)


def test_symetrie_h_rotation(monkeypatch):
    from chrysalide.arc3.logique.induction import induire
    tr = Tr([((1, F, x, 1),) for x in range(3)], [4, 4])  # seule la flèche droite a été vue, pas de 1
    monkeypatch.setenv("CHRYS_SYMETRIE", "1")
    th, _ = induire([(tr, None, None)], limite_s=10)
    assert th.moves.get((1, 1)) == (0, -1) and th.moves_supposes.get((1, 1)) in ("H_rotation", "H_partage", "H_oppose")
    assert th.moves.get((1, 3)) == (-1, 0)


def test_poursuivant_hors_contrat():
    # le mobile 1 avance sous la flèche ; l'objet 2 le poursuit (autonome) : il a bougé, sans loi de flèche
    tr = Tr([((1, F, 0, 1), (2, F, 5, 1)), ((1, F, 1, 1), (2, F, 4, 1)), ((1, F, 2, 1), (2, F, 3, 1))], [4, 4])
    th = Theorie(moves={(1, 4): (1, 0)}, autonomes={2: 1})
    _, raison = predire(th, Connaissance(tr, range(2)), ((1, F, 0, 1), (2, F, 7, 1)), 4, tr.taille)
    assert raison is None or "c2" not in raison


def test_mdl_comprime():
    from chrysalide.arc3.logique.mdl import comprime, mdl
    tr = _couloir()  # le mobile 1 avance deux fois vers la droite
    tr.fond = 0
    tr.cases = [Theorie().rendu(e, tr.taille, 0) for e in tr.etats]
    bonne, vide = Theorie(moves={(1, 4): (1, 0)}), Theorie()
    assert mdl(bonne, tr)[2] == 0 and mdl(vide, tr)[2] > 0  # la bonne loi n'a aucune exception
    assert comprime(bonne, tr)[0] and not comprime(vide, tr)[0]


def test_cases_inconnues():
    from chrysalide.arc3.logique.prediction import cases_inconnues
    deux = frozenset({(0, 0), (1, 0)})  # mobile de 2 cases : (0, 1)-(1, 1), puis (1, 1)-(2, 1)
    tr = Tr([((1, deux, 0, 1),), ((1, deux, 1, 1),)], [4], taille=(4, 3))
    assert cases_inconnues(tr) == frozenset({(1, 1)})  # x=1 couverte aux deux images ; x=2 vue dégagée à t=0
