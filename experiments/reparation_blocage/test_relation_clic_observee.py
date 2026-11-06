import copy,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from relation_clic_observee import actualiser,proposer_agent
from session_chaine_generique import agent_transfere
from chaine_agent_integree import AgentIntegre
from issues_observees import issue_sdk


def trace(n):
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_victoire30/partie'
    rows=json.loads(p.with_suffix('.json').read_text())['rows'][:n]
    with np.load(p.with_suffix('.npz')) as z:
        a=SimpleNamespace(images=list(z['images'][:n+1].copy()),actions=[r['action'] for r in rows],
            films=[z[f'film_{i+1}'].copy() for i in range(n)],
            issues=[issue_sdk(r['state'],r['levels_completed'],0) for r in rows],
            modele_gagnant=None,commandes_connues=set(),graine_exploration=0)
    return a


def avancer_trace(a,n):
    b=trace(n);a.images=b.images;a.actions=b.actions;a.films=b.films;a.issues=b.issues


def test_relation_apprise_et_confirmee_prospectivement():
    a=trace(24);d=proposer_agent(a,[6]);assert d['actions']==[['clic',30,19]]
    assert a.memoire_relation_clic['regle']['ratio']==2
    avancer_trace(a,25);d=proposer_agent(a,[6]);assert d['origine']=='relation_clic_marqueur_confirme'
    assert d['actions']==[['clic',42,18]]
    avancer_trace(a,26);actualiser(a)
    assert a.memoire_relation_clic['validations_prospectives'][-1]=={'coup':26,'exact':True}


def test_contradiction_suspend_la_regle():
    a=trace(24);proposer_agent(a,[6]);avancer_trace(a,25);proposer_agent(a,[6]);avancer_trace(a,26)
    a.images[-1]=a.images[-1].copy();a.images[-1][30:45,:]=10
    a.films[-1][-1]=a.images[-1]
    assert proposer_agent(a,[6]) is None
    assert a.memoire_relation_clic['refutee']


def test_transfert_partiel_pas_but_ni_mutation_source():
    a=trace(30);avant=copy.deepcopy(vars(a));n=agent_transfere(a,a.images[-1],[1,2,3,4,6,7])
    assert n.actions==[] and n.modele_gagnant is None and n.theorie_precedente is None
    assert n.memoire_relation_clic['but_certifie'] is False
    assert n.memoire_relation_clic['preuves_niveau_precedent']==[21,24,26,28]
    assert vars(a).keys()==avant.keys()
    assert proposer_agent(n,[6]) is not None


def test_transfert_sans_victoire_refuse():
    a=trace(28)
    with pytest.raises(ValueError,match='Victoire réelle'):agent_transfere(a,a.images[-1],[6])


def test_decider_raccord_et_ablation(monkeypatch):
    import relation_clic_observee as module
    t=trace(24)
    def agent():
        a=AgentIntegre(t.images,t.actions,t.films,t.issues,limite=1000,exploration_p1=True)
        a.reconstruction=False
        return a
    d=agent().decider([6],secondes=0)
    monkeypatch.setattr(module,'proposer_agent',lambda *args:None)
    autre=agent().decider([6],secondes=0)
    assert d['origine']=='relation_clic_observee'
    assert autre['origine']!='relation_clic_observee' and d['actions']!=autre['actions']


def test_sans_clic_aucune_action():
    assert proposer_agent(trace(24),[1,2,3,4]) is None


def test_transfert_partiel_preserve_flags_explicitement_actifs():
    a=trace(30);a.composition_contextuelle_auto=True;a.recherche_prolongee=True
    n=agent_transfere(a,a.images[-1],[6])
    assert n.composition_contextuelle_auto and n.recherche_prolongee
    a.composition_contextuelle_auto=False;a.recherche_prolongee=False
    n=agent_transfere(a,a.images[-1],[6])
    assert not n.composition_contextuelle_auto and not n.recherche_prolongee


def test_factory_cpu_prolonge_opt_in():
    from session_chaine_generique import nouvel_agent,configurer_recherche,arguments_session
    t=trace(0);a=nouvel_agent(t.images,[],[],[])
    assert not a.recherche_prolongee
    args=arguments_session().parse_args(['--jeu','inconnu','--neuf','--sortie','sans_sdk','--recherche-prolongee'])
    assert configurer_recherche(a,activation=args.recherche_prolongee)


def test_selection_sans_marqueur_evite_repetition_avant_masque_compteur():
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_trace10/partie'
    rows=json.loads(p.with_suffix('.json').read_text())['rows']
    with np.load(p.with_suffix('.npz')) as z:
        def etat(n):
            return SimpleNamespace(images=list(z['images'][:n+1].copy()),
                actions=[r['action'] for r in rows[:n]],films=[z[f'film_{i+1}'].copy() for i in range(n)],
                issues=['continue']*n)
        a=etat(4);d=proposer_agent(a,[6]);assert d['actions']==[['clic',38,16]]
        b=etat(5);a.images=b.images;a.actions=b.actions;a.films=b.films;a.issues=b.issues
    autre=proposer_agent(a,[6])
    assert autre['actions']!=d['actions']
    assert autre['source']==(43,15)
    preuve=a.memoire_relation_clic['sondes_selection_non_confirmees'][-1]
    assert preuve['coup']==5 and 'pas_preuve_impossibilite' in preuve['portee']


def test_transfert_partiel_redecouvre_commandes_non_couvertes():
    a=trace(30);a.commandes_connues={1,2,3,4,7}
    n=agent_transfere(a,a.images[-1],[1,2,3,4,6,7])
    assert n.commandes_connues==a.commandes_connues
    assert n.sondes_contexte==[1,2,3,4,7]
    d=n.decider([1,2,3,4,6,7],secondes=0)
    assert d['actions']==[1] and d['statut']=='experience_contexte_commande'
    n.observer(1,n.images[-1].copy(),np.asarray([n.images[-1]]),'continue')
    assert n.decider([1,2,3,4,6,7],secondes=0)['actions']==[2]
    assert 1 not in n.sondes_contexte # pas de répétition automatique de la même sonde
    assert agent_transfere(a,a.images[-1],[6]).sondes_contexte==[]
