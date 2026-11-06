"""Contrats de raccordement, sans jeu ARC ni synthétique exécuté."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parent / 'paquet')]

from chaine_coherente import Chaine

from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.moteur import MoteurFormel


def exemple():
    def image(x):
        g = np.zeros((64, 64), dtype=int)
        g[1, 6] = 9
        g[1, x] = 3
        return g.tolist()

    th = Theorie(moves={(3, 4): (1, 0)}, but=('sortie', 3, 9))
    programme, non = exporter(th, (64, 64))
    assert not non
    c = Chaine(MoteurFormel(), programme, [image(3), image(4)],
               [{'actions': [{'action': 'RIGHT'}]}], [('RIGHT',)], coups_deja_joues=1)
    return c, image


def test_perception_compilation_plan_et_observation():
    c, image = exemple()
    r = c.proposer()
    assert r['statut'] == 'plan_simule_valide', r
    assert len(r['plan']['actions']) == 2
    obs = c.observer(('RIGHT',), image(5))
    assert obs['statut'] == 'transition_confirmee'
    assert c.plan is None
    assert c.proposer()['statut'] == 'plan_simule_valide'
    obs = c.observer(('RIGHT',), image(6), victoire=True, source='trace')
    assert obs['statut'] == 'victoire_verifiee_sur_trace'


def test_surprise_revoque_le_plan_et_refute_le_modele():
    c, image = exemple()
    c.proposer()
    obs = c.observer(('RIGHT',), image(4))
    assert obs['statut'] == 'modele_refute'
    assert c.refute and c.plan is None
    assert c.proposer()['statut'] == 'modele_invalide'
    assert len(c.contre_exemples) == 1


def test_patch_regressif_refuse_sans_detruire_la_reference():
    c, _ = exemple()
    c.proposer()
    ancien = copy.deepcopy(c.programme)
    plan = copy.deepcopy(c.plan)
    noms = [r['nom'] for r in c.programme['regles'] if r['nom'].startswith('move')]
    assert noms
    r = c.patch(f'REPONSE = Reponse(patch=Patch(retire={noms!r}, ajoute=[]))')
    assert r['statut'] == 'patch_refuse'
    assert c.programme == ancien and c.plan == plan and c.version == 1


def test_revision_acceptee_invalide_les_descendants():
    c, _ = exemple()
    c.proposer()
    r = c.patch('REPONSE = Reponse(patch=Patch(retire=[], ajoute=[Regle("annotation", quand=False, alors=[])]))')
    assert r['statut'] == 'patch_valide_sur_observations'
    assert c.version == 2 and c.plan is None


def test_mutation_hors_revision_refusee():
    c, image = exemple()
    c.proposer()
    c.programme['etat']['modification_externe'] = True
    assert c.observer(('RIGHT',), image(5))['statut'] == 'modele_modifie_hors_revision'


def test_python_libre_refuse():
    c, _ = exemple()
    assert c.patch('import os\nos.system("true")')['statut'] == 'patch_refuse'


def test_but_atteint_sans_victoire_ne_vaut_pas_victoire():
    c, image = exemple()
    c.proposer()
    c.observer(('RIGHT',), image(5))
    c.proposer()
    r = c.observer(('RIGHT',), image(6), victoire=False)
    assert r['statut'] == 'but_refute' and c.refute


def test_ia_non_appelee_si_enumeration_non_tentee():
    c, _ = exemple()

    def interdit(*args, **kwargs):
        raise AssertionError('Ne doit pas appeler le modele')

    assert c.demander_patch(interdit)['statut'] == 'enumeration_deterministe_requise'


def test_sortie_ia_utilise_le_meme_lecteur_et_rejette_python_libre():
    c, image = exemple()
    c.proposer()
    c.observer(('RIGHT',), image(4))

    def faux_client(prompt, **kwargs):
        assert 'semantique_native' in prompt and 'differences' in prompt
        assert kwargs['modele'] == 'qwen3.8:27b-mlx'
        return '```python\nimport os\n```', {'test_transport': True}

    r = c.demander_patch(faux_client, enumeration_infructueuse=True)
    assert r['statut'] == 'patch_refuse' and c.refute


def test_cache_compilation_isole_et_invalide_a_la_revision():
    c, _ = exemple()
    rapport, courant = c.rejouer()
    assert rapport['compilation_fidele']
    courant[0].etat['mutation_branche'] = True
    courant[1].sprites[0]['x'] = 999
    rapport2, courant2 = c.rejouer()
    assert rapport2['cache_verifie']
    assert 'mutation_branche' not in courant2[0].etat
    assert all(s['x'] != 999 for s in courant2[1].sprites)
    c.patch('REPONSE = Reponse(patch=Patch(retire=[], ajoute=[Regle("annotation", quand=False, alors=[])]))')
    assert c._verifie is None


def test_contre_exemple_echange_sans_devenir_loi_universelle():
    from chrysalide.langue.theorie_contrats import depuis_contrats, vers_contrats
    th = Theorie(moves={(3, 4): (1, 0)})
    monde = ((3, frozenset({(0, 0)}), 4, 1),)
    th.sans_effet = frozenset({th.cle_sans_effet(monde, 4, (64, 64))})
    contrats = vers_contrats(th)
    assert 'sans_effet' not in contrats['non_exprimes']
    observation = [i for i in contrats['instances'] if i['champ'] == 'sans_effet']
    assert len(observation) == 1 and observation[0]['section'] == 'observation'
    assert depuis_contrats(contrats).sans_effet == th.sans_effet


@pytest.mark.parametrize('methode', ['nmcs', 'aleatoire'])
def test_montecarlo_utilise_le_meme_programme_compile(methode):
    c, _ = exemple()
    r = c.proposer(methode=methode, secondes=.1)
    assert r['statut'] == 'plan_simule_valide'
    assert len(r['plan']['actions']) == 2
    assert r['infos']['backend'] == 'ProgrammeCompile'


def test_portefeuille_existant_borne_a_deux_processus():
    c, _ = exemple()
    r = c.proposer(methode='portefeuille', secondes=.5)
    assert r['statut'] == 'plan_simule_valide', r.get('infos', {}).get('termines')
    assert r['infos']['processus'] == 2
    assert r['infos']['cpu_total_mesure'] >= r['infos']['cpu_enfants']
