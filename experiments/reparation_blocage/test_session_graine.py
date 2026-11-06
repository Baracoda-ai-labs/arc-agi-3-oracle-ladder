"""Contrôles sans SDK : graine explorateur et comptabilité session."""
import io
import json
from types import SimpleNamespace
import numpy as np
import pytest
import session_chaine_generique as session
import exploration_p1_prefixe as exploration


def test_proposeur_transmet_graine_sans_sdk(monkeypatch):
    graines=[]
    class Faux:
        def __init__(self, lab, _, graine):
            graines.append(graine);self.valeur={};self.trace=[]
        def choisir(self):return 1,'test'
    monkeypatch.setattr(exploration,'GrapheIntegral',Faux)
    for graine in (0,7):
        d=exploration.proposer([np.zeros((2,2))],[],[],[1],graine=graine)
        assert d['graine_exploration']==graine
    assert graines==[0,7]


def test_session_neuve_journal_et_cout_sans_sdk(tmp_path,monkeypatch):
    class FauxLabo:
        def __init__(self,jeu,niveau,dossier,output):
            self.output=output;output.parent.mkdir(parents=True)
            self.level=1;self.rows=[];self.finished=False;self.won=False
            self.completed_baseline=0;self.partie_gagnee=False;self.actions_disponibles=[1]
            self.images=[np.zeros((2,2),dtype=int)];self.films={}
        def play(self,action,purpose):
            self.rows.append(dict(action=action,state='NOT_FINISHED',levels_completed=0))
            self.images.append(self.images[-1].copy());self.films[f'film_{len(self.rows)}']=np.array([self.images[-1]])
            np.savez(self.output.with_suffix('.npz'),images=self.images,**self.films)
    class FauxAgent:
        def __init__(self,*args,**kwargs):
            self.graine_exploration=kwargs['graine_exploration'];self.journal=[];self.chaines={};self.revisions=0
    monkeypatch.setattr(session,'LaboP1',FauxLabo)
    monkeypatch.setattr(session,'AgentIntegre',FauxAgent)
    monkeypatch.setattr(session,'empreintes',lambda *args:{})
    monkeypatch.setattr(session.sys,'stdin',io.StringIO('{"op":"close"}\n'))
    monkeypatch.setattr(session.time,'process_time',lambda:10.)
    calls=iter([3.,8.,9.]);monkeypatch.setattr(session,'cpu_enfants',lambda:next(calls))
    args=SimpleNamespace(jeu=next(iter(session.AUTORISES)),sortie=tmp_path/'run',neuf=True,
      graine=7,prefixe=None,archives_niveaux=None,transfert_depuis=None,source=None)
    session.main(args)
    state=json.loads((args.sortie/'etat.json').read_text())
    journal=json.loads((args.sortie/'journal.json').read_text())
    assert state['graine_exploration']==7 and not state['sdk_seed_appliquee']
    configurations=[e for e in journal if e.get('type')=='configuration_graine']
    assert len(configurations)==1
    assert configurations[0]['graine_exploration']==7
    assert configurations[0]['sdk_seed_appliquee'] is False
    assert state['cpu_s']==state['cpu_parent_s']==0
    assert state['cpu_enfants_recoltes_s']==state['cpu_total_recolte_s']==6


def test_metadonnees_reprise_et_refus_resemer(tmp_path):
    (tmp_path/'etat.json').write_text(json.dumps({'graine_exploration':11}))
    b={};assert session.lire_graine(tmp_path,b)==11
    assert b['graine_exploration']==11
    with pytest.raises(ValueError,match='reprise conserve'):
        session.main(SimpleNamespace(jeu=next(iter(session.AUTORISES)),graine=1,neuf=False))


def test_cpu_enfants_compte_utilisateur_et_systeme(monkeypatch):
    monkeypatch.setattr(session.resource,'getrusage',lambda who:SimpleNamespace(ru_utime=3.,ru_stime=2.))
    assert session.cpu_enfants()==5.


def test_transfert_conserve_graine_sans_sdk(monkeypatch):
    import transfert_modele_c
    def creer(*args,**kwargs):
        return SimpleNamespace(graine_exploration=kwargs.get('graine_exploration',0),journal=[])
    monkeypatch.setattr(session,'nouvel_agent',creer)
    monkeypatch.setattr(transfert_modele_c,'reaffecter',lambda *args,**kwargs:(SimpleNamespace(perception=SimpleNamespace(th_releve=None)),{}))
    ancien=SimpleNamespace(graine_exploration=19,modele_gagnant=SimpleNamespace(
        perception=SimpleNamespace(th_plan=None,th_releve=None),grilles=[],lots=[],
        films=SimpleNamespace(entrees=[])),precedents=[],actions=[1],commandes_connues={1})
    a=session.agent_transfere(ancien,np.zeros((2,2)),[1])
    assert a.graine_exploration==19


def test_ancien_agent_sans_attribut_graine_repli_decider(monkeypatch):
    """Objet ancien désérialisé : ne pas migrer ni réécrire son payload."""
    import chaine_agent_integree as chaine
    a=chaine.AgentIntegre([np.zeros((2,2),dtype=int)],[],[],[],exploration_p1=True)
    del a.graine_exploration
    a.reconstruction=False
    monkeypatch.setattr(a,'_relever_p1',lambda *args:None)
    monkeypatch.setattr(a,'_suivre_experience',lambda *args:None)
    monkeypatch.setattr(a,'dossier',lambda offre:SimpleNamespace(signature=lambda:'prefixe'))
    monkeypatch.setattr(chaine.Controleur,'decider',lambda *args,**kwargs:{})
    graines=[]
    def proposer(*args,graine):
        graines.append(graine)
        return {'actions':[1],'predictions':[[]],'statut':'experience_conditionnelle'}
    monkeypatch.setattr(exploration,'proposer',proposer)
    assert a.decider([1])['actions']==[1]
    assert graines==[0]
    assert not hasattr(a,'graine_exploration')
