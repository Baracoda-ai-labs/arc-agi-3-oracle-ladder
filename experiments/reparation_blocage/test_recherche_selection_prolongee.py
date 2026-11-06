from types import SimpleNamespace
import pytest
import recherche_selection_prolongee as mod

class Chaine:
    def __init__(self):
        self.perception=mod.SelectionObservee.__new__(mod.SelectionObservee)
        self.plan=None; self.refute=False; self.programme={'regles':[]};self.actions=[('UP',)]
        self.revision=0;self.valides=True;self.adoptions=[]
    def signature(self):return {'revision':self.revision}
    def rejouer(self):return {k:True for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')}, object()
    def verifier_plan(self,p):return self.valides,{}
    def adopter_plan(self,p,origine):
        self.adoptions.append(p);self.plan={'actions':p};return {'statut':'plan_simule_valide'}

def contexte():
    c=Chaine();a=SimpleNamespace(chaines={'c':c},journal=[])
    return a,c

def echec(c):return {'c':{'refus':'budget','signature':mod.signature_recherche(c,[1])}}

def resultats(plan=None):
    return [{'plan':plan,'poids':3,'preuve':{},'cpu_s':2}, {'plan':None,'poids':10,'preuve':{},'cpu_s':3}]

def test_adoption_validee_cpu_et_pas_sdk(monkeypatch):
    a,c=contexte();monkeypatch.setattr(mod,'_executer',lambda *x:resultats([('UP',)]))
    r=mod.prolonger(a,[1],echec(c))
    assert r['statut']=='plan_simule_valide' and c.adoptions==[[('UP',)]]
    assert r['cpu_enfants_s']==5 and r['cpu_total_s']>=5 and r['sdk_actions']==0
    assert r['cpu_complet'] is True

@pytest.mark.parametrize('mutation',['programme','etat','objet'])
def test_resultat_perime(monkeypatch,mutation):
    a,c=contexte()
    def execution(*x):
        if mutation=='programme':c.programme['regles'].append('nouvelle')
        elif mutation=='etat':c.revision+=1
        else:a.chaines['c']=Chaine()
        return resultats([('UP',)])
    monkeypatch.setattr(mod,'_executer',execution)
    assert mod.prolonger(a,[1],echec(c))['statut']=='resultat_perime'
    assert not c.adoptions

def test_plan_invalide_rejete_et_signature_non_repetee(monkeypatch):
    a,c=contexte();c.valides=False;calls=[]
    monkeypatch.setattr(mod,'_executer',lambda *x:(calls.append(1) or resultats([('UP',)])))
    assert mod.prolonger(a,[1],echec(c))['statut']=='aucun_plan_valide'
    assert mod.prolonger(a,[1],echec(c))['statut']=='aucun_palier_eligible'
    c.revision+=1
    mod.prolonger(a,[1],echec(c))
    assert len(calls)==2 and not c.adoptions

@pytest.mark.parametrize('cas',['absence','epuise','perime','plan','refute','famille'])
def test_pas_de_recherche_sans_contrat(monkeypatch,cas):
    a,c=contexte();e=echec(c)
    if cas=='absence':e={}
    elif cas=='epuise':e['c']['refus']='espace_epuise'
    elif cas=='perime':c.revision+=1
    elif cas=='plan':c.plan={'actions':[('UP',)]}
    elif cas=='refute':c.refute=True
    else:c.perception=object()
    monkeypatch.setattr(mod,'_executer',lambda *x:pytest.fail('recherche indue'))
    assert mod.prolonger(a,[1],e)['statut'] in ('aucun_palier_eligible','plan_deja_present')

def test_deux_travailleurs_reutilises(monkeypatch):
    saved=[];jobs=[]
    a,c=contexte()
    def portefeuille(taches,valider):
        jobs.extend(taches)
        assert valider([('UP',)])
        return resultats()
    monkeypatch.setattr(mod,'portefeuille',portefeuille)
    monkeypatch.setattr(mod,'sauver_agent',lambda a,p:saved.append(p))
    mod._executer(a,'c',120)
    assert len(saved)==1 and [j[2:] for j in jobs]==[(3,120),(10,120)]

@pytest.mark.parametrize('active',[True,False])
def test_decider_raccord_avant_repli(monkeypatch,active):
    import numpy as np
    import chaine_agent_integree as module
    a=module.AgentIntegre([np.zeros((8,8),int)],[],[],[])
    a.reconstruction=False;a.recherche_prolongee=active
    c=Chaine();c.proposer=lambda **kw:{'statut':'aucun_plan_retourne'}
    c._tracer_plan=lambda:None
    a.chaines={'c':c}
    monkeypatch.setattr(module,'chercher',lambda *args,**kw:(None,{'refus':'budget'}))
    monkeypatch.setattr(a,'dossier',lambda offre:SimpleNamespace(signature=lambda:'prefixe'))
    monkeypatch.setattr(module.Controleur,'decider',lambda *args,**kw:{})
    monkeypatch.setattr(a,'_predire',lambda *args:{'issue':None,'image':[[0]]})
    appels=[]
    def prolonger(agent,offre,echecs):
        appels.append(echecs)
        assert echecs['c']['signature']==mod.signature_recherche(c,offre)
        c.plan={'actions':[('UP',),('DOWN',)]}
        return {'statut':'plan_simule_valide','modele':'c'}
    monkeypatch.setattr(mod,'prolonger',prolonger)
    # Si le plan prolongé ne prend pas le relais, ce repli explicitement activé tranche.
    a.revision_solidite=True
    monkeypatch.setattr(a,'_sonder_revision',lambda offre:{'statut':'repli','actions':[]})
    d=a.decider([1,2],secondes=1)
    assert bool(appels)==active
    assert d['statut']==('action_conditionnelle' if active else 'repli')
    if active:
        assert d['actions']==[1] and d['suite_plan']==[('DOWN',)] and a.attente is d


def test_nouvel_agent_recherche_inactive_sans_opt_in():
    import numpy as np
    from session_chaine_generique import nouvel_agent
    assert not nouvel_agent([np.zeros((8,8),int)],[],[],[]).recherche_prolongee
