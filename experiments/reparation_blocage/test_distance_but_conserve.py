import copy

from chaine_coherente import Chaine
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.plan_langage import planifier_langage
from chrysalide.arc3.sim_rapide import cloner
from distance_but_conserve import pour_chaine
from test_transfert_modele_c import source


def cas():
    s, _ = source()
    vue = copy.deepcopy(s.perception)
    vue.th_releve.but = ('marques', ((2, ((12, 8),)),), None)
    programme, non = exporter(vue.th_releve, vue.tr.taille)
    assert not non
    c = Chaine(vue, programme, s.grilles, [], [('RIGHT',)], reserve=20)
    return c


def test_score_decroit_avant_couverture_sans_modifier_etat():
    c = cas()
    _, (pc, sc) = c.rejouer()
    distance = pour_chaine(c)
    avant = distance(sc, pc.etat)
    s2, e2 = cloner(sc, pc.etat)
    pc.etat = e2
    pc.step(s2, ('RIGHT',))
    assert s2.issue is None
    assert 0 < distance(s2, pc.etat) < avant
    assert distance(sc, {}) == avant


def test_callback_ne_peut_pas_inventer_victoire():
    c = cas()
    _, (pc, sc) = c.rejouer()
    actions, infos = planifier_langage(c.programme, sc, [('SPACE',)],
        noeuds=20, secondes=1, compiler=False, etat=pc.etat, estimer=lambda sc, etat: 0)
    assert actions is None


def test_plan_sur_simulateur_conserve_verifie_et_sans_callback_inchange():
    c = cas()
    signature = c.signature()
    for score in (None, pour_chaine(c)):
        _, (pc, sc) = c.rejouer()
        actions, infos = planifier_langage(c.programme, sc, c.actions,
            noeuds=20, secondes=1, compiler=False, etat=pc.etat, estimer=score)
        assert actions == [('RIGHT',), ('RIGHT',)]
        assert c.verifier_plan(actions)[0]
        assert c.signature() == signature
