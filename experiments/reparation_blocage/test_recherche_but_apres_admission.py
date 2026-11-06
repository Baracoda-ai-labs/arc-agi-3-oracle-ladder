from types import SimpleNamespace
import numpy as np
from chaine_agent_integree import AgentIntegre
import buts_modele_conserve
import perception_clics_couples
import chrysalide.arc3.moteur as moteur


def agent():
    return AgentIntegre([np.zeros((4,4),dtype=int)]*9,[1]*8,[None]*8,
                        ['continue']*8,exploration_p1=True,utilite_sondes=True)


def test_admission_recherche_unique_sans_reinduction_et_budget_nul_preserve(monkeypatch):
    a=agent();appels=[];inductions=[]
    candidat=SimpleNamespace(refute=False,plan=None,rejouer=lambda:({'catalogue_shacl':True},object()))
    class M:
        def __init__(self,**kw):self.infos={}
        def proposer(self,h):inductions.append(h);return None
    monkeypatch.setattr(moteur,'MoteurC',M)
    monkeypatch.setattr(buts_modele_conserve,'chercher',lambda cs,*args,**kw:(appels.append(tuple(cs)) or (None,[])))
    monkeypatch.setattr(perception_clics_couples,'proposer',lambda *args,**kw:[candidat])
    a._relever_p1(3,[6])
    assert a.releves_p1=={1} and a._buts_en_attente()
    a._relever_p1(0,[6]);assert a._buts_en_attente()
    a._relever_p1(3,[6]);a._relever_p1(3,[6])
    assert appels==[(),('perception_clics/0',)] and len(inductions)==1
    assert not a._buts_en_attente()


def test_migration_snapshot_et_decider_preserve_modeles(monkeypatch):
    import sondes_portefeuille
    a=agent();del a.recherche_buts_en_attente
    a.releves_p1={1};a.chaines={'neuf':SimpleNamespace(refute=False,plan=None)}
    a.journal=[{'type':'buts_modele_conserve'},
               {'type':'admission','nom':'neuf','controle':{'catalogue_shacl':True}}]
    assert a._buts_en_attente()
    monkeypatch.setattr(a,'reconstruire',lambda:(_ for _ in ()).throw(AssertionError('reconstruction')))
    appels=[]
    monkeypatch.setattr(buts_modele_conserve,'chercher',lambda cs,*args,**kw:(appels.append(tuple(cs)) or (None,[])))
    monkeypatch.setattr(moteur,'MoteurC',lambda **kw:(_ for _ in ()).throw(AssertionError('induction')))
    monkeypatch.setattr(sondes_portefeuille,'proposer',lambda *args:{'statut':'sonde_test'})
    assert a.decider([6])['statut']=='sonde_test'
    assert appels==[('neuf',)] and not a._buts_en_attente() and a.releves_p1=={1}


def test_ancien_snapshot_deja_recherche_ou_admission_refutee_ne_reouvre_pas():
    a=agent();del a.recherche_buts_en_attente
    a.chaines={'neuf':SimpleNamespace(refute=True)}
    a.journal=[{'type':'buts_modele_conserve'},
               {'type':'admission','nom':'neuf','controle':{'catalogue_shacl':True}}]
    assert not a._buts_en_attente()
    a.chaines['neuf'].refute=False
    a.journal.append({'type':'buts_modele_conserve'})
    assert not a._buts_en_attente()
