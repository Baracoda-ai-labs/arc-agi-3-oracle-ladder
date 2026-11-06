"""Propositions de code et expériences, avec les interpréteurs existants."""
import copy
import sys
from pathlib import Path

import pytest

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / 'paquet/livraison_p1/code'))
from chaine_coherente import Chaine
from propositions_python import Proposition
from test_chaine_coherente import exemple

OUTIL = '''PROGRAMME = Programme(regles=[], fonctions={"changements": {
"params": ["films"], "expr": "sum(1 for t in range(1,len(films)) for i in range(len(films[0])) if films[t][i]!=films[t-1][i])"}})'''
EXP = '''PROGRAMME = Programme(regles=[], experience={"actions": [["RIGHT"],["RIGHT"]],
"question": "Le mouvement reste-t-il possible au prochain contact ?"})'''


def deux_modeles():
    c, _ = exemple()
    p = copy.deepcopy(c.programme)
    r = next(r for r in p['regles'] if r['nom'].startswith('move'))
    # Hypothèse alternative jouet : même passé, mouvement bloqué depuis x=4.
    r['quand'] = ['et', r['quand'], ['non', ['existe', '$o', ['objets', {'couleur': 3}], ['=', ['x', '$o'], 4]]]]
    d = Chaine(c.perception, p, c.grilles, c.lots, c.actions, coups_deja_joues=c.coups)
    return {'libre': c, 'bloque': d}


def test_outil_sur_film_transitoire_malgre_image_finale_identique():
    p = Proposition(OUTIL)
    r = p.tester_outil('changements', [(([[0, 0], [1, 0], [0, 0]],), 2), (([[0], [0]],), 0)])
    assert r['statut'] == 'tests_conformes'


def test_experience_reutilise_partition_et_tronque_au_premier_coup():
    chaines = deux_modeles()
    anciens = [copy.deepcopy(c.programme) for c in chaines.values()]
    r = Proposition(EXP).evaluer_experience(chaines)
    assert r['statut'] == 'experience_discriminante_simulee'
    assert r['evaluation']['info'] == 1 and r['cout_coups_prefixe'] == 1
    assert not r['droit_action'] and r['nouveaux_coups_reels'] == 0
    assert [c.programme for c in chaines.values()] == anciens


def test_etat_cache_seul_ne_compte_pas_comme_information():
    c, _ = exemple(); d = copy.deepcopy(c)
    d.programme['etat']['invisible'] = 7
    from chaine_coherente import empreinte
    d.modele_sha = empreinte(d.programme)
    r = Proposition(EXP).evaluer_experience({'a': c, 'b': d})
    assert r['statut'] == 'sans_information_visible'


@pytest.mark.parametrize('source', ['import os\nPROGRAMME=Programme(regles=[])',
    'PROGRAMME=Programme(regles=[Regle("x",quand=True,alors=[gagner()])])',
    'PROGRAMME=Programme(regles=[],fonctions={"interdit":{"params":[],"expr":"open(1)"}})'])
def test_code_hors_contrat_refuse(source):
    with pytest.raises(ValueError):
        Proposition(source)


def test_refus_budget_hypothese_refutee_et_action_inconnue():
    for variante in ('reserve', 'refutee', 'action'):
        chaines = deux_modeles()
        c = chaines['libre']
        if variante == 'reserve': c.limite = c.coups
        if variante == 'refutee': c.refute = True
        if variante == 'action': c.actions = []
        with pytest.raises(ValueError):
            Proposition(EXP).evaluer_experience(chaines)


def test_allocation_excessive_et_poids_non_calibres_refuses():
    p = Proposition('PROGRAMME=Programme(regles=[],fonctions={"enorme":{"params":[],"expr":"[0]*20000"}})')
    assert p.tester_outil('enorme', [((), [])])['statut'] == 'outil_refuse'
    with pytest.raises(ValueError):
        Proposition(EXP).evaluer_experience(deux_modeles(), poids={'libre': 0, 'bloque': 1})


def test_deux_historiques_distincts_non_comparables():
    chaines = deux_modeles()
    chaines['libre'].coups += 1
    with pytest.raises(ValueError, match='meme historique'):
        Proposition(EXP).evaluer_experience(chaines)
