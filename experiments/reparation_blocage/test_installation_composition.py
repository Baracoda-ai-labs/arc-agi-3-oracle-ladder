"""Admission en mémoire : rejet atomique, isolation, conservation des sources."""
from pathlib import Path
import copy
import cloudpickle
import numpy as np
import pytest
from preparer_agent_composition import installer_composition

R=Path(__file__).parent/'runs'

def charger():
    a=cloudpickle.loads((R/'ar25_retour_apres_mouvement51/agent.pkl').read_bytes())
    c=cloudpickle.loads((R/'ar25_composition_contextes52/candidat_plan.pkl').read_bytes())
    return a,c

def test_installation_isolee_et_memoire_conservee():
    a,c=charger(); anciens=set(a.chaines); actions=copy.deepcopy(a.actions)
    check=installer_composition(a,c)
    assert check['compilation_fidele']
    assert a.actions==actions and a.chaines['contextes_observes'] is not c
    assert set(a.memoires_avant_composition[-1]['chaines'])==anciens
    assert a.memoires_avant_composition[-1]['modeles_suspendus']
    assert a.memoire_jeu is None and not a.modeles_contextes_suspendus
    assert a.chaines['contextes_observes'].verifier_plan(c.plan['actions'])[0]

def test_rejet_sans_perte_sur_observation_differente():
    a,c=charger(); a.images[-1]=np.zeros_like(a.images[-1]).tolist()
    chaines=a.chaines; suspendus=a.modeles_contextes_suspendus; n=len(a.journal)
    with pytest.raises(ValueError,match='non alignee'): installer_composition(a,c)
    assert a.chaines is chaines and a.modeles_contextes_suspendus is suspendus
    assert len(a.journal)==n and not hasattr(a,'memoires_avant_composition')


def charger_portefeuille():
    a=cloudpickle.loads((R/'ar25_memoire_episodes52_1/agent.pkl').read_bytes())
    cs={nom:cloudpickle.loads((R/'ar25_composition_calques_integrale52'/f'{nom}.pkl').read_bytes())
        for nom in ('detail_local','detail_periodique')}
    return a,cs


def test_portefeuille_repare_isole_planifie_sans_effacer_memoire():
    a,cs=charger_portefeuille();source=cloudpickle.dumps(cs);episodes=a.observations_episodes
    check=installer_composition(a,cs)
    assert check['candidats']==2 and set(a.chaines)==set(cs)
    assert a.observations_episodes is episodes
    assert a.memoires_avant_composition[-1]['modeles_suspendus']
    for nom,c in a.chaines.items():
        assert c is not cs[nom] and c.programme==cs[nom].programme
        assert c.rejouer()[0]['transitions']==52
        plan=c.proposer(secondes=.5)
        assert plan['statut']=='plan_simule_valide',plan
        assert c.verifier_plan(c.plan['actions'])[0]
    assert cloudpickle.dumps(cs)==source


def test_portefeuille_rejete_atomiquement_si_second_invalide():
    a,cs=charger_portefeuille();cs['detail_periodique'].grilles[-1][10][10]=2
    chaines=a.chaines;suspendus=a.modeles_contextes_suspendus;journal=copy.deepcopy(a.journal)
    with pytest.raises(ValueError,match='non alignee'):installer_composition(a,cs)
    assert a.chaines is chaines and a.modeles_contextes_suspendus is suspendus
    assert a.journal==journal and not hasattr(a,'memoires_avant_composition')


def test_wrapper_inconnu_ou_preuve_desynchronisee_refuse():
    from types import SimpleNamespace
    a,cs=charger_portefeuille();c=cs['detail_local']
    c.perception=SimpleNamespace(preuve={'commutation_dynamique_apprise':True})
    with pytest.raises(ValueError,match='Wrapper'):installer_composition(a,[c])
    a,cs=charger_portefeuille()
    cs['detail_local'].perception.base.vue_composee.preuve['commandes']['0']=('UP',)
    with pytest.raises(ValueError,match='non synchronisee'):installer_composition(a,cs)
    assert a.modeles_contextes_suspendus
