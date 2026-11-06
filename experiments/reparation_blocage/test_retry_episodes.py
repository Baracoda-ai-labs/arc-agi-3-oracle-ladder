import io,json
import pytest
from types import SimpleNamespace
import numpy as np
import session_chaine_generique as s
import exploration_p1_prefixe as p1
from memoire_episodes import retenir_defaite,risques,separer_episode


def test_risque_provisoire_prefere_alternative_mais_ne_bannit_pas(monkeypatch):
    image=np.zeros((64,64),dtype=int)
    agent=SimpleNamespace(images=[image,image],actions=[1],issues=['defaite'])
    preuves=retenir_defaite(agent,[1,2],1)
    class Ex:
        def __init__(self,*args,**kwargs):self.valeur={};self.trace=[];self.aretes={}
        def cle(self,im):return "etat"
        def choisir(self):return 1,'explorer'
        def candidats(self,im):return [1,2]
        def priorite(self,a,im):return 0
    monkeypatch.setattr(p1,'GrapheIntegral',Ex)
    d=p1.proposer([image],[],[],[1,2],memoire_episodes=preuves)
    assert d['actions']==[2] and d['memoire_defaites_provisoire']
    assert not risques(preuves,image,[1])  # offre différente : pas de causalité supposée
    assert not risques(preuves,np.ones_like(image),[1,2])
    assert p1.proposer([image],[],[],[1,2])['actions']==[1]


@pytest.mark.parametrize('commandes',[
    '{"op":"retry"}\n{"op":"advance","coups":1}\n',
    '{"op":"auto","lots":2,"coups":1,"reprises":true}\n'])
def test_retry_deux_episodes_compte_reset_sans_transition_fictive(tmp_path,monkeypatch,commandes):
    image=np.zeros((64,64),dtype=int);env=object();calls=[]
    class Lab:
        def __init__(self,jeu,niveau,dossier,output):
            self.env=env;self.level=1;self.output=output;output.parent.mkdir(parents=True)
            self.image=image;self.images=[image];self.rows=[];self.films={};self.actions_disponibles=[1,2]
            self.finished=False;self.won=False;self.partie_gagnee=False;self.completed_baseline=0
            self.resets=0;self.defaites=0
        def save(self):
            np.savez(self.output.with_suffix('.npz'),images=self.images,**self.films)
            self.output.with_suffix('.json').write_text(json.dumps(self.rows))
        def play(self,act,purpose):
            calls.append(act);self.won=act==2;self.partie_gagnee=self.won
            self.rows.append(dict(action=act,state='WIN' if self.won else 'GAME_OVER',levels_completed=int(self.won)))
            self.images.append(image);self.films[f'film_{len(self.rows)}']=np.array([image])
            self.finished=True;self.save();return image,np.array([image])
        def reset_apres_defaite(self,purpose):
            calls.append(0);self.rows.append(dict(action=0,state='NOT_FINISHED',levels_completed=0))
            self.images.append(image);self.films[f'film_{len(self.rows)}']=np.array([image])
            self.finished=False;self.resets+=1;self.save();return image
    class Agent:
        def __init__(self,images,actions,films,issues,**kwargs):
            self.images=list(images);self.actions=list(actions);self.issues=list(issues)
            self.journal=[];self.chaines={};self.revisions=0;self.commandes_connues=set();self.precedents=[]
        def decider(self,offre,*args,**kwargs):
            risks=risques(getattr(self,'memoire_episodes',[]),self.images[-1],offre)
            return {'actions':[next(a for a in offre if a not in risks)],'statut':'experience'}
        def observer(self,action,im,film,issue):
            self.actions.append(action);self.images.append(im);self.issues.append(issue);return {}
    monkeypatch.setattr(s,'LaboP1',Lab);monkeypatch.setattr(s,'AgentIntegre',Agent)
    monkeypatch.setattr(s,'empreintes',lambda *args:{})
    monkeypatch.setattr(s.sys,'stdin',io.StringIO(commandes+'{"op":"close"}\n'))
    args=SimpleNamespace(jeu=next(iter(s.AUTORISES)),sortie=tmp_path/'run',neuf=True,graine=0,
      prefixe=None,archives_niveaux=None,transfert_depuis=None,source=None)
    s.main(args)
    state=json.loads((args.sortie/'etat.json').read_text())
    assert calls==[1,0,2] and state['coups_reels']==3 and state['initialisations']==1
    assert state['resets_retry']==1 and state['tentative']==2
    assert state['jeu_gagne'] and state['niveaux_gagnes']==1
    from avancer_agent_relais import charger_agent
    ancien=charger_agent(args.sortie/'N1/agent_avant_retry_1.pkl')
    assert ancien.issues[-1]=='defaite'
    first=json.loads((args.sortie/'N1/partie.json').read_text())
    second=json.loads((args.sortie/'N1/tentative_2/partie.json').read_text())
    assert [r['action'] for r in first]==[1,0] and [r['action'] for r in second]==[2]
    with np.load(args.sortie/'N1/tentative_2/partie.npz') as z:assert len(z['images'])==2


def test_memoire_ne_reanime_pas_graphe_epuise_ni_action_mortelle(monkeypatch):
    image=np.zeros((64,64),dtype=int)
    preuves=retenir_defaite(SimpleNamespace(images=[image,image],actions=[1],issues=['defaite']),[1,2,3],1)
    class Ex:
        raison='explorer'
        def __init__(self,*args,**kwargs):self.valeur={};self.trace=[];self.aretes={'etat':{2:'mort',3:'etat'}}
        def cle(self,im):return 'etat'
        def choisir(self):return 1,self.raison
        def candidats(self,im):return [1,2,3]
        def priorite(self,a,im):return a
    monkeypatch.setattr(p1,'GrapheIntegral',Ex)
    assert p1.proposer([image],[],[],[1,2,3],memoire_episodes=preuves)['actions']==[1]
    Ex.raison='graphe_epuise_aleatoire'
    assert p1.proposer([image],[],[],[1,2,3],memoire_episodes=preuves) is None
