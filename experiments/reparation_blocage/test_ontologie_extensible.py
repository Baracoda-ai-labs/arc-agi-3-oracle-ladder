"""Dépendances, abstention et contre-exemples indépendants de l'ajustement."""
import copy
import json

import pytest
from chaine_coherente import Chaine
from ontologie_extensible import ExtensionCandidate, FicheRevision
from test_chaine_coherente import exemple

from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.langue import vers_python


def fiche(th):
    return FicheRevision(th, ['RIGHT'], {'modele': str(th)})


def test_pas_de_famille_navigation_sans_but_malgre_deplacement():
    r = fiche(Theorie(moves={(3, 4): (1, 0)})).rapport()
    assert [c['famille'] for c in r['candidats']] == ['inconnue']
    assert not r['probabilites_calibrees'] and not r['droit_action']


def test_rapport_serialisable_avec_empreintes_non_rectangulaires():
    r = fiche(Theorie(formes={3: frozenset({(0, 0), (1, 0)})})).rapport()
    assert json.loads(json.dumps(r))['contrats']['instances']


def test_hypothese_deplacement_non_promue_en_verite_et_revoquee():
    f = fiche(Theorie(moves={(3, 4): (1, 0)}, moves_supposes={(3, 4): 'H_partage'}, but=('sortie', 3, 9)))
    r = f.rapport()
    assert r['candidats'][0]['famille'] == 'navigation_sortie'
    assert any(c['section'] == 'hypothese' for c in r['contrats']['instances'])
    f.revoquer()
    assert f.rapport()['candidats'] == []


def test_familles_multiples_et_indices_non_devines():
    th = Theorie(moves={(3, 4): (1, 0)}, poussables={4}, but=('sortie', 3, 9), selection_clic=(3, 0, 0))
    f = FicheRevision(th, ['RIGHT', 'CLICK'], {'modele': 'x'})
    assert {c['famille'] for c in f.rapport()['candidats']} == {'pousse_cibles', 'selection_deplacement'}
    assert not f.rapport()['signaux']['modele_visible']
    with pytest.raises(ValueError):
        FicheRevision(th, [], {}, modele_visible='oui')


def test_clic_canonique_et_contrat_de_voisinage_raccordes():
    th = Theorie(bascule={3: 4}, motif={(0, 0), (1, 0)})
    r = FicheRevision(th, ['MOUSE'], {}).rapport()
    assert r['candidats'][0]['famille'] == 'interrupteurs_clic'
    assert r['signaux']['propagation_voisins']


def test_transfert_reutilise_separation_des_parametres_et_ne_garde_pas_les_instances():
    r = fiche(Theorie(moves={(3, 4): (1, 0)})).rapport()
    t = r['transfert_candidat'][0]
    assert t['garde']['params'] == {'dx': 1, 'dy': 0}
    assert {'classe', 'action', '_brut'} <= set(t['recalcule'])
    assert not r['transfert_confirme']


def chaines_disjointes():
    c, image = exemple()
    d = Chaine(c.perception, c.programme, [image(4), image(5)], c.lots, c.actions)
    return c, d


def test_extension_passe_developpement_et_reserve_sans_mutation():
    c, d = chaines_disjointes()
    avant = copy.deepcopy((c.programme, d.programme))
    e = ExtensionCandidate(vers_python(c.programme), ['deplacement'], 'interjeux')
    r = e.verifier([c], [d])
    assert r['statut'] == 'compatible_sur_traces', r
    assert not r['transfert_demontre'] and not r['droit_action']
    assert (c.programme, d.programme) == avant


def test_extension_fausse_refusee_sur_transition_reservee():
    c, d = chaines_disjointes()
    p = copy.deepcopy(c.programme)
    move = next(r for r in p['regles'] if r['nom'].startswith('move'))
    move['quand'] = ['et', move['quand'], ['non', ['existe', '$o', ['objets', {'couleur': 3}], ['=', ['x', '$o'], 4]]]]
    r = ExtensionCandidate(vers_python(p), ['deplacement', 'blocage'], 'niveau').verifier([c], [d])
    assert r['statut'] == 'refusee'
    assert r['rapports'][0]['conforme'] and not r['rapports'][1]['conforme']


def test_reserve_dupliquee_refusee_meme_sous_un_autre_objet():
    c, _ = chaines_disjointes()
    e = ExtensionCandidate(vers_python(c.programme), ['deplacement'], 'jeu')
    with pytest.raises(ValueError, match='deja vues'):
        e.verifier([c], [copy.deepcopy(c)])


def test_primitive_inconnue_et_python_libre_refuses():
    with pytest.raises(ValueError):
        ExtensionCandidate('PROGRAMME=Programme(regles=[])', ['invention'], 'jeu')
    with pytest.raises((ValueError, SyntaxError)):
        ExtensionCandidate('import os', ['deplacement'], 'jeu')


def test_chaine_abstention_apres_patch_ou_refutation():
    c, _ = exemple()
    c.perception.th_plan = Theorie(moves={(3, 4): (1, 0)}, but=('sortie', 3, 9))
    assert c.classifier()['candidats'][0]['famille'] == 'navigation_sortie'
    c.refute = True
    assert c.classifier()['statut'] == 'modele_invalide'
    c.refute, c.version = False, 2
    assert c.classifier()['statut'] == 'contrats_a_reextraire_apres_revision'
