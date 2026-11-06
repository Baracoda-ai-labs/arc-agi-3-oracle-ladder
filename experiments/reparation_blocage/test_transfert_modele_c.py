import copy

import numpy as np
import pytest

from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.logique.export_langage import exporter
from transfert_modele_c import reaffecter


def source():
    g = np.zeros((64, 64), dtype=int)
    g[8:11, 8:11] = 1
    g[24:27, 24:27] = 2
    tr = Trajectoire([g.tolist()], [], ech=(1, 0, 0))
    th = Theorie(moves={(1, 4): (1, 0)}, but=('sortie', 1, 2))
    m = MoteurC()
    m.tr, m.th_releve, m._couches = tr, th, th.couches()
    p, non = exporter(th, tr.taille)
    assert not non
    return Chaine(m, p, [g.tolist()], [], [('RIGHT',)], coups_deja_joues=44), g


def test_nouvelle_instance_sans_etats_n1_et_regles_conservees():
    s, g = source()
    original = copy.deepcopy(s.perception.th_releve)
    signature = s.signature()
    g2 = np.roll(g, 5, axis=0)
    s.perception._index = {'ancien': 4}
    s.perception.tr.grilles = [g.tolist(), g.tolist()]
    c, diag = reaffecter(s, g2, [('RIGHT',)], coups_deja_joues=45, reserve=100)
    assert c.perception.th_releve == original
    assert s.perception.th_releve == original and s.signature() == signature
    assert c.coups == 45 and c.limite == 100
    assert len(c.grilles) == len(c.perception.tr.grilles) == len(c.perception.tr.etats) == 1
    assert c.lots == c.perception.tr.actions == c.films.entrees == []
    assert c.plan is None and c.contre_exemples == []
    assert np.array_equal(c.grilles[0], g2)
    assert c.perception.tr.etats[0] != s.perception.tr.etats[0]
    assert diag['regles_reapprises'] == diag['transitions_nouveau_niveau'] == 0
    assert not diag['promotion_durable'] and diag['mouvements_conserves']


def test_parametres_locaux_inconnus_ne_detruisent_pas_mouvements():
    s, g = source()
    th = s.perception.th_releve
    th.but = ('copie', ((2, frozenset({(24, 24)})),))
    th.jauge = (9, 1)
    s.programme, _ = exporter(th, s.perception.tr.taille)
    from chaine_coherente import empreinte
    s.modele_sha = empreinte(s.programme)
    c, diag = reaffecter(s, g, [('RIGHT',)])
    assert c.perception.th_releve.moves == th.moves
    assert c.perception.th_releve.but is None and not c.perception.th_releve.jauge
    assert set(diag['parametres_non_reaffectes']) == {'jauge', 'but_coordonnees'}
    assert th.but is not None and th.jauge == (9, 1)


def test_source_desynchronisee_refusee():
    s, g = source()
    s.perception.th_releve.solides = frozenset({2})
    with pytest.raises(ValueError, match='synchronisée'):
        reaffecter(s, g, [('RIGHT',)])


@pytest.mark.parametrize('boites', [False, True])
def test_hitbox_transferee_reinduite_et_exportee_sans_muter_source(boites, monkeypatch):
    from chrysalide.arc3.logique.induction import induire
    from chrysalide.arc3.logique.hitbox_formes import etendre_observations
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene, rendre
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.sim_rapide import ProgrammeCompile

    monkeypatch.setenv('CHRYS_MARQUEUR', '0')
    monkeypatch.setenv('CHRYS_PAIRES_COULEUR', '0')
    croix = frozenset({(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)})
    g = np.zeros((64, 64), dtype=int)
    for x, y in croix:
        g[8+y, 8+x] = 14
    tr = Trajectoire([g.tolist()], [], ech=(1, 0, 0))
    tr.diagonales = frozenset({14, 15})
    tr.marqueurs = frozenset()
    tr.etats = [tr.etat(g)]
    tr._bruts = list(tr.etats)
    th = Theorie(motif=frozenset({(0, 0)}), bascule={14: 15, 15: 14},
                 formes_bascule=frozenset({croix}),
                 hitbox_formes=frozenset({croix}) if boites else frozenset())
    tr.hitbox_formes = th.hitbox_formes
    m = MoteurC()
    m.tr, m.th_releve, m._couches = tr, th, th.couches()
    programme, non = exporter(th, tr.taille)
    assert not non
    s = Chaine(m, programme, [g.tolist()], [], [('clic', 8, 8)])
    signature, origine = s.signature(), copy.deepcopy(s.perception.th_releve)
    g2 = np.roll(g, 12, axis=1)
    c, _ = reaffecter(s, g2, [('clic', 20, 8), ('clic', 21, 8)])
    local = c.perception.tr
    assert local.hitbox_formes == th.hitbox_formes
    assert local.diagonales == tr.diagonales
    assert len(local.etats) == 1
    # Une observation sur un pixel puis une prédiction inédite dans le creux.
    apres = g2.copy()
    apres[apres == 14] = 15
    etendre_observations(local, [g2.tolist(), apres.tolist()], [('clic', 20, 8)])
    revisee, _ = induire(local, anciennes=c.perception.th_releve, limite_s=2)
    assert revisee.hitbox_formes == th.hitbox_formes
    monde = local.etats[0]
    attendu = revisee.rendu(revisee.clic(monde, 21, 8), local.taille, local.fond)
    assert np.count_nonzero(attendu != g2) == (5 if boites else 0)
    texte, non = exporter(revisee, local.taille)
    assert not non
    for executant in (Programme, ProgrammeCompile):
        scene = Scene(local.taille, local.fond, local.fond,
                      [dict(_sprite(o), couche=0) for o in monde])
        executant(texte).step(scene, ('MOUSE', 8, 21))
        assert np.array_equal(rendre({'vue': scene.vue, 'fond': scene.fond,
            'letterbox': local.fond, 'sprites': scene.sprites}), attendu)
    assert s.signature() == signature and s.perception.th_releve == origine
    assert s.perception.tr.hitbox_formes == th.hitbox_formes
    assert np.array_equal(s.grilles[0], g)


def test_but_marques_reaffecte_sans_changer_contrat_ni_mouvements(monkeypatch):
    from chaine_coherente import empreinte
    monkeypatch.setenv('CHRYS_PAIRES_COULEUR', '0')
    s, g = source()
    th = s.perception.th_releve
    th.but = ('marques', ((4, ((12, 12),)),), 'couleur')
    s.programme, _ = exporter(th, s.perception.tr.taille)
    s.modele_sha = empreinte(s.programme)
    g[40, 41] = 4
    c, diag = reaffecter(s, g, [('RIGHT',)])
    assert c.perception.th_releve.but == ('marques', ((4, ((41, 40),)),), 'couleur')
    assert c.perception.th_releve.moves == th.moves
    assert th.but == ('marques', ((4, ((12, 12),)),), 'couleur')
    assert diag['but_reaffecte_depuis_nouvelle_image']


def test_porteur_diagonal_reaffecte_classe_sans_reapprendre_lois(monkeypatch):
    monkeypatch.setenv('CHRYS_DIAGONALES', '0')
    monkeypatch.setenv('CHRYS_PAIRES_COULEUR', '0')
    g = np.full((64, 64), 5, dtype=int)
    g[10, 8:13] = 11
    g[8:13, 10] = 11
    g[10, 10] = 0
    g[30, 30] = 4
    tr = Trajectoire([g.tolist()], [], ech=(1, 0, 0))
    tr.marqueur, tr.marqueurs = True, frozenset({0})
    tr.etats = [tr.etat(g)]
    piece = next(o for o in tr.etats[0] if o[0] == 11)
    th = Theorie(moves={(512, 4): (1, 0)}, porteur=(512, 5),
        hotes=frozenset({(11, piece[1])}), but=('marques', ((4, ((30, 30),)),), None))
    m = MoteurC()
    m.tr, m.th_releve, m._couches = tr, th, th.couches()
    p, non = exporter(th, tr.taille)
    assert not non
    s = Chaine(m, p, [g.tolist()], [], [('RIGHT',), ('SPACE',)])
    nouveau = np.full((64, 64), 5, dtype=int)
    for d in range(-3, 4):
        nouveau[20+d, 20+d] = nouveau[20+d, 20-d] = 12
    nouveau[20, 20] = 0
    nouveau[40, 40] = 13
    c, diag = reaffecter(s, nouveau, [('RIGHT',), ('SPACE',)])
    assert diag['diagonales_instance'] == [12]
    assert diag['hotes_sous_marqueur'] == [12]
    assert c.perception.th_releve.moves == th.moves
    assert c.perception.th_releve.porteur == th.porteur
    assert {k for k, _ in c.perception.th_releve.hotes} == {12}
    assert c.perception.th_releve.but == ('marques', ((13, ((40, 40),)),), None)
    assert th.hotes == frozenset({(11, piece[1])})
    _, courant = c.rejouer()
    pc, scene = courant
    pc.step(scene, ('RIGHT',))
    image = c.perception.rendu(scene)
    assert image[20, 21] == 0 and image[17, 18] == 12
