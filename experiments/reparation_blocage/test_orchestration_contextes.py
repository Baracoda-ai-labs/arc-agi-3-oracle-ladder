from pathlib import Path
import cloudpickle,copy
import orchestration_contextes as module
from correspondance_contextes_objets import reaffecter_observation

R=Path(__file__).parent

def agent():
    a=cloudpickle.loads((R/'runs/ar25_memoire_episodes52_1/agent.pkl').read_bytes())
    a.composition_contextuelle_auto=True
    return a


def test_decider52_installe_et_planifie_deux_hypotheses_sans_sdk():
    a=agent();images=cloudpickle.dumps(a.images);episodes=cloudpickle.dumps(a.observations_episodes)
    d=a.decider(list(range(1,8)),secondes=15)
    assert d['statut']=='action_conditionnelle',d
    assert len(a.chaines)==2 and len(d['modeles'])==2 and d['suite_plan']
    assert all(c.rejouer()[0]['transitions']==52 for c in a.chaines.values())
    assert cloudpickle.dumps(a.images)==images and cloudpickle.dumps(a.observations_episodes)==episodes
    assert a.memoires_avant_composition[-1]['modeles_suspendus']
    assert any(r.get('installe') for r in a.journal if r.get('type')=='orchestration_contextes')


def test_espace_epuise_signe_seconde_passe_sans_recursion():
    a=agent();source=next(iter(a.modeles_contextes_suspendus.values()))['chaine']
    c,diag=reaffecter_observation(source,a.images[-1]);assert c is not None,diag
    a.chaines={'principal':c};a.modeles_contextes_suspendus={};a.diagnostic_transfert=None
    a.exploration_p1=False;a.utilite_sondes=False;a.reconstruction=False
    d=a.decider(list(range(1,8)),secondes=15)
    assert d['statut']=='action_conditionnelle' and len(a.chaines)==2
    assert a.epuisements_contextuels['principal']['infos']['refus']=='espace épuisé'


def test_opt_in_cache_et_banque_absente(monkeypatch):
    a=agent();del a.composition_contextuelle_auto
    assert module.orchestrer(a,5)['refus']=='option_inactive'
    a.composition_contextuelle_auto=True
    appels=[]
    def absent(*args,**kwargs):appels.append(True);return [],{'statut':'aucun'}
    monkeypatch.setattr(module,'proposer_segments',absent)
    assert not module.orchestrer(a,5)['installe']
    assert module.orchestrer(a,5)['refus']=='essai_identique_deja_effectue' and len(appels)==1
    a.observations_episodes=[]
    assert module.orchestrer(a,5)['refus']=='banque_absente'


def test_preuve_espace_perimee_ne_declenche_pas():
    a=agent();c=next(iter(a.modeles_contextes_suspendus.values()))['chaine']
    a.chaines={'principal':c};a.modeles_contextes_suspendus={}
    module.enregistrer_epuisement(a,'principal',c,{'infos':{'refus':'espace épuisé'}})
    a.images[-1]=a.images[-1].copy();a.images[-1][10,10]=2
    assert module.orchestrer(a,5)['refus']=='aucun_declencheur_signe'


def test_budget_nul_sans_installation_ni_calcul(monkeypatch):
    a=agent();avant=a.modeles_contextes_suspendus
    monkeypatch.setattr(module,'proposer_segments',lambda *x,**kw: (_ for _ in ()).throw(AssertionError('induction interdite')))
    r=module.orchestrer(a,0)
    assert not r['installe'] and r['refus']=='budget_avant_selection'
    assert a.modeles_contextes_suspendus is avant and not a.chaines


def test_budget_selection_interne_repris_seulement_si_budget_augmente(monkeypatch):
    a=agent();appels=[]
    def selection(*args,**kwargs):
        appels.append(kwargs['secondes'])
        return [],{'budget_epuise':True}
    monkeypatch.setattr(module,'proposer_segments',selection)
    assert module.orchestrer(a,1)['refus']=='budget_selection'
    assert module.orchestrer(a,1)['refus']=='essai_identique_deja_effectue'
    assert len(appels)==1
    assert module.orchestrer(a,2)['refus']=='budget_selection'
    assert len(appels)==2


def test_budget_composition_interne_repris_seulement_si_budget_augmente(monkeypatch):
    from types import SimpleNamespace
    a=agent();appels=[]
    monkeypatch.setattr(module,'proposer_segments',lambda *x,**kw: ([SimpleNamespace(preuve_segment_contextuel={})],{}))
    def composition(*args,**kwargs):
        appels.append(kwargs['secondes'])
        return [],{'refus':'budget_selection'}
    monkeypatch.setattr(module,'proposer_avec_revision',composition)
    assert module.orchestrer(a,1)['refus']=='budget_composition'
    assert module.orchestrer(a,1)['refus']=='essai_identique_deja_effectue'
    assert len(appels)==1
    assert module.orchestrer(a,2)['refus']=='budget_composition'
    assert len(appels)==2
