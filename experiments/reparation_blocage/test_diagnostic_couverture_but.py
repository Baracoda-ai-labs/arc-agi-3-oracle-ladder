import copy
from test_extension_but_relationnel import exemple
from diagnostic_couverture_but import diagnostiquer


def test_couverture_partielle_avec_dynamique_exacte_ne_confirme_pas_but():
    g, tr, th = exemple()
    original = copy.deepcopy(th)
    d = diagnostiquer(th, tr, [g, g.copy()], [{'image_exacte': True, 'pixels_ecart': 0}])
    c = d['couverture'][0]
    assert c['centres_couverts'] == 1 and c['centres_non_couverts_candidats'] == 1
    assert c['extensions'][0]['centres_candidats'] == 2
    assert c['extensions'][0]['role_neutre'] == 'hypothese_non_confirmee'
    assert {e['role_propose'] for e in c['extensions']} == {'meme','autre','neutre'}
    assert all(e['centres_candidats']==2 and e['roles_non_confirmes'] for e in c['extensions'])
    assert not d['but_confirme'] and not d['promotion_durable']
    assert d['dynamique']['statut'] == 'compatible_sur_observations'
    assert th == original


def test_dynamique_refutee_distincte_de_couverture_incomplete():
    g, tr, th = exemple()
    d = diagnostiquer(th, tr, [g, g.copy()], [{'image_exacte': False, 'pixels_ecart': 9}])
    assert d['dynamique']['statut'] == 'refutee_sur_observations'
    assert d['couverture'][0]['diagnostic_alphabet'] == 'incomplet_possible'


def test_marque_mobile_et_absence_cible_ne_prouvent_pas_completude():
    g, tr, th = exemple()
    avant = g.copy(); avant[4, 14] = 2
    d = diagnostiquer(th, tr, [avant, g])
    assert d['couverture'][0]['extensions'] == []
    assert d['couverture'][0]['diagnostic_alphabet'] == 'indetermine'
    assert d['dynamique']['statut'] == 'non_evaluee'
    d = diagnostiquer(th, tr, [])
    assert d['couverture'][0]['centres_couverts'] == 0
    assert not d['but_confirme']
