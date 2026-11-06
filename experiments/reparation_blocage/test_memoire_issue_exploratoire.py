import copy
from types import SimpleNamespace
from test_chaine_coherente import exemple
from memoire_issue_exploratoire import capturer,memoriser


def avant_victoire():
    c,image=exemple()
    c.proposer()
    c.observer(('RIGHT',),image(5))
    return c,image


def test_sonde_victorieuse_unique_reutilise_validation_sans_owner():
    c,image=avant_victoire();decision={'actions':[4],'modeles':['c']}
    original=copy.deepcopy(c.grilles)
    p,models,nom=capturer({'c':c},decision,('RIGHT',),image(6),[image(6)],'niveau',3,source='trace')
    assert nom=='c' and p['source']=='trace'
    assert p['candidats'][0]['but_confirme_par_prediction']
    assert models['c'].grilles==original and c.grilles==original
    models['c'].grilles.append(image(6))
    assert c.grilles==original


def test_victoire_ne_confirme_pas_but_non_predit():
    c,image=exemple()  # Encore deux actions jusqu'au but modèle, mais issue observée après une.
    a=SimpleNamespace(chaines={'c':c},attente={'actions':[4],'modeles':['c']},
        actions=[4],journal=[],modele_gagnant='ancien_niveau')
    p=memoriser(a,('RIGHT',),image(5),[image(5)],'niveau',source='jeu')
    assert a.modele_gagnant is None and 'c' in a.modeles_avant_victoire
    assert p['but_reste_a_induire'] and not p['candidats'][0]['but_confirme_par_prediction']
    assert a.journal[-1]['issue']=='niveau' and not p['promotion_interjeux']


def test_deux_predictions_gagnantes_ne_choisissent_pas_arbitrairement():
    c,image=avant_victoire()
    p,models,nom=capturer({'a':c,'b':copy.deepcopy(c)},{'actions':[4],'modeles':['a','b']},
        ('RIGHT',),image(6),[image(6)],'victoire',3,source='trace')
    assert nom is None and p['ambiguite'] and len(models)==2
    assert all(x['but_confirme_par_prediction'] for x in p['candidats'])


def test_modele_refute_non_transmis_et_pas_de_capture_non_terminale():
    c,image=avant_victoire();c.refute=True
    p,models,nom=capturer({'c':c},{'actions':[4],'modeles':['c']},('RIGHT',),image(6),[image(6)],'niveau',3,source='trace')
    assert not models and nom is None and p['but_reste_a_induire']
    assert capturer({}, {}, ('RIGHT',),image(6),[image(6)],'continue',3,source='trace')==(None,{},None)


def test_raccord_agent_observer_capture_sonde_avant_terminal():
    from chaine_agent_integree import AgentIntegre
    c,image=avant_victoire();c.activer_atms()
    a=AgentIntegre(c.grilles,[4,4],[[image(4)],[image(5)]],['continue','continue'],limite=100)
    a.chaines={'c':c};a.attente={'actions':[4],'modeles':['c'],'predictions':[[]]}
    a.observer(4,image(6),[image(6)],'niveau',source='trace')
    assert a.modele_gagnant is not None
    assert len(a.modele_gagnant.grilles)==3 and len(a.images)==4
    preuves=[r for r in a.journal if r['type']=='memoire_issue_observee']
    assert preuves[-1]['source']=='trace' and preuves[-1]['selection']=='c'
