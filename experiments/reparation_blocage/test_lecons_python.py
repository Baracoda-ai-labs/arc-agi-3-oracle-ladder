"""Même leçon paramétrique, scènes distinctes, fausses préconditions et faux statuts."""
import copy
from pathlib import Path

import numpy as np
import pytest
from chaine_coherente import Chaine
from lecons_python import LeconPython
from test_chaine_coherente import exemple

from chrysalide.arc3.langage import ErreurLangage
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.moteur import MoteurFormel

SOURCE = Path(__file__).with_name('exemple_lecon.py').read_text()
VALEURS = {'mobile': 3, 'cible': 9}


def test_aller_retour_lecon_et_plan_verifie_sans_mutation():
    l = LeconPython(SOURCE)
    ll = LeconPython(l.python())
    assert (l.meta, l.corps, l.condition) == (ll.meta, ll.corps, ll.condition)
    c, _ = exemple()
    avant = copy.deepcopy((c.programme, c.grilles, c.plan, c.version))
    r = l.evaluer_strategie(c, VALEURS)
    assert r['resultat']['statut'] == 'plan_simule_valide', r
    assert len(r['resultat']['plan']['actions']) == 2
    assert not r['droit_action'] and not r['transfert_reel_demontre']
    assert (c.programme, c.grilles, c.plan, c.version) == avant


def test_meme_lecon_sur_autre_scene_couleurs_et_positions_sans_edition():
    def image(x):
        g = np.zeros((64, 64), dtype=int)
        g[4, 12], g[4, x] = 8, 5
        return g.tolist()
    p, refus = exporter(Theorie(moves={(5, 4): (1, 0)}, but=('sortie', 5, 8)), (64, 64))
    assert not refus
    c = Chaine(MoteurFormel(), p, [image(8), image(9)],
               [{'actions': [{'action': 'RIGHT'}]}], [('RIGHT',)])
    r = LeconPython(SOURCE).evaluer_strategie(c, {'mobile': 5, 'cible': 8})
    assert r['resultat']['statut'] == 'plan_simule_valide'
    assert len(r['resultat']['plan']['actions']) == 3


def test_precondition_absente_interdit_la_recherche(monkeypatch):
    c, _ = exemple()
    def interdit(*args, **kwargs):
        raise AssertionError('Aucune recherche si la precondition manque')
    monkeypatch.setattr(Chaine, 'proposer', interdit)
    r = LeconPython(SOURCE).evaluer_strategie(c, {**VALEURS, 'cible': 7})
    assert r['statut'] == 'precondition_non_satisfaite'


@pytest.mark.parametrize('source', [
    SOURCE.replace('statut="propose"', 'statut="confirme"'),
    SOURCE.replace('version=1', 'version=1, version=2'),
    SOURCE.replace('"mobile", "cible"', '"mobile"'),
    SOURCE.replace('y(a) == y(b)', 'y(inconnu) == y(b)'),
    SOURCE.replace('y(a) == y(b)', 'meme_ligne(a, b)'),
    SOURCE.replace('"methode": "but"', '"methode": "but", "secondes": 999'),
    SOURCE.replace('regles=[]', 'regles=[Regle("r", quand=True, alors=[deplacer(inconnu, 1, 0)])]'),
    SOURCE.replace('corps=y(a) == y(b)', 'corps=y(a) == y(b), promesse=True'),
    SOURCE.replace('regles=[]', 'regles=[Regle("r", quand=True, alors=[], autres={"statut":"confirme"})]'),
    SOURCE.replace('"methode": "but"', '"methode": "but", "methode": "cegar"'),
    'import os\n' + SOURCE,
    SOURCE + '\nLECON = Lecon()\n',
])
def test_propositions_invalides_refusees(source):
    with pytest.raises((ValueError, ErreurLangage)):
        LeconPython(source)


def test_liaison_complete_et_collision_de_nom_refusees():
    l = LeconPython(SOURCE)
    c, _ = exemple()
    with pytest.raises(ValueError):
        l.instancier(c, {'mobile': {'couleur': 3}})
    c.programme['mots'] = copy.deepcopy(l.corps['mots'])
    with pytest.raises(ValueError, match='masquer'):
        l.instancier(c, VALEURS)


def test_modele_refute_ne_peut_produire_de_strategie():
    c, _ = exemple()
    c.refute = True
    assert LeconPython(SOURCE).evaluer_strategie(c, VALEURS)['statut'] == 'modele_invalide'


def test_dossier_llm_effectivement_lisible_et_refus_explicite():
    c, _ = exemple()
    d = c.dossier_lecon()
    assert LeconPython(d['exemple_lisible']).meta['statut'] == 'propose'
    r = c.evaluer_lecon(d['exemple_lisible'], VALEURS)
    assert r['resultat']['statut'] == 'plan_simule_valide'
    assert c.evaluer_lecon('import os', {})['statut'] == 'lecon_refusee'


def test_regle_ecrite_en_python_est_instanciee_dans_le_meme_programme():
    source = SOURCE.replace('regles=[]',
        'regles=[Regle("memoire_observee", quand=True, alors=[poser("memoire_lecon", 1)], puis="continuer")]')
    c, _ = exemple()
    l = LeconPython(source)
    p = l.instancier(c, VALEURS)
    candidat = Chaine(c.perception, p, c.grilles, c.lots, c.actions)
    controle, etat = candidat.rejouer()
    assert controle['compilation_fidele'] and etat[0].etat['memoire_lecon'] == 1
    assert 'memoire_lecon' not in c.programme.get('etat', {})
