"""Pilotage automatique : faux laboratoire, aucune instance SDK."""
from types import SimpleNamespace
import pytest
from session_chaine_generique import piloter_auto

class Faux:
    def __init__(self,issues):
        self.issues=iter(issues);self.lab=SimpleNamespace(won=False,finished=False,partie_gagnee=False,level=1)
        self.coups=0;self.transferts=0;self.env=object()
    def avancer(self,n):
        for _ in range(n):
            self.coups+=1
            issue=next(self.issues,'continue')
            self.lab.won=issue in ('niveau','victoire')
            self.lab.finished=issue!='continue'
            self.lab.partie_gagnee=issue=='victoire'
            if self.lab.finished:break
        return 'lot_termine_session_conservee'
    def suivant(self):
        assert self.lab.won and not self.lab.partie_gagnee
        self.transferts+=1;self.lab.level+=1
        self.lab.won=self.lab.finished=False


def test_auto_multiniveau_termine_exactement_fin_lot():
    f=Faux(['continue','niveau','continue','victoire'])
    env=f.env
    assert piloter_auto(lambda:f.lab,f.avancer,f.suivant,lots=3,coups=2)=='jeu_gagne'
    assert (f.coups,f.transferts,f.lab.level)==(4,1,2)
    assert f.env is env


def test_fin_lots_reprenables_pas_defaite():
    f=Faux([])
    assert piloter_auto(lambda:f.lab,f.avancer,f.suivant,lots=2,coups=3)=='auto_lots_termines_session_conservee'
    assert f.coups==6 and not f.lab.finished
    piloter_auto(lambda:f.lab,f.avancer,f.suivant,lots=1,coups=2)
    assert f.coups==8


def test_defaite_et_absence_action_conservent_sans_reset():
    f=Faux(['defaite'])
    assert piloter_auto(lambda:f.lab,f.avancer,f.suivant,lots=10)=='defaite_sdk'
    assert f.coups==1 and f.transferts==0
    g=Faux([]);calls=[]
    def diagnostic(n):calls.append(n);return 'hypotheses_ambigues'
    assert piloter_auto(lambda:g.lab,diagnostic,g.suivant,lots=10)=='hypotheses_ambigues'
    assert len(calls)==1 and g.transferts==0


def test_transfert_ambigu_preserve_niveau_gagne():
    f=Faux(['niveau']);f.avancer(1)
    def ambigu():raise ValueError('Modèle gagnant absent')
    with pytest.raises(ValueError,match='Modèle gagnant absent'):
        piloter_auto(lambda:f.lab,f.avancer,ambigu,lots=2)
    assert f.lab.won and f.lab.level==1 and f.coups==1


@pytest.mark.parametrize('lots,coups',[(0,1),(1,0),(True,1),(1,1.5)])
def test_bornes_validees_avant_action(lots,coups):
    f=Faux([])
    with pytest.raises(ValueError):piloter_auto(lambda:f.lab,f.avancer,f.suivant,lots=lots,coups=coups)
    assert f.coups==0


def test_commande_auto_session_reutilise_sdk_et_compte_coups(tmp_path,monkeypatch):
    import io,json
    import numpy as np
    import session_chaine_generique as s
    instances=[];transferts=[]
    class Lab:
        def __init__(self,jeu,niveau,dossier,output):
            self.env=object();self.level=niveau;self.output=output
            self.rows=[];self.completed_baseline=0;self.won=False;self.finished=False
            self.partie_gagnee=False;self.actions_disponibles=[1]
            self.image=np.zeros((2,2),dtype=int);self.images=[self.image];self.films={}
            output.parent.mkdir(parents=True);instances.append(self)
        def play(self,action,purpose):
            self.image=np.full((2,2),self.level,dtype=int);self.images.append(self.image)
            self.won=self.level==2 or len(self.rows)==2
            self.finished=self.won;self.partie_gagnee=self.won and self.level==2
            self.rows.append(dict(action=action,state='WIN' if self.partie_gagnee else 'NOT_FINISHED',
                levels_completed=self.level if self.won else self.level-1))
            film=np.array([self.image]);self.films[f'film_{len(self.rows)}']=film
            np.savez(self.output.with_suffix('.npz'),images=self.images,**self.films)
            return self.image,film
        def next_level(self,output):
            assert self.won
            nxt=Lab('test',2,None,output);nxt.env=self.env;nxt.image=self.image
            nxt.completed_baseline=1
            return nxt
    class Agent:
        def __init__(self,*args,**kwargs):self.journal=[];self.chaines={};self.revisions=0
        def decider(self,*args,**kwargs):return dict(actions=[1],statut='experience')
        def observer(self,*args):return {'observe':True}
    def transfert(ancien,image,offre):
        transferts.append(image.copy());return Agent()
    monkeypatch.setattr(s,'LaboP1',Lab);monkeypatch.setattr(s,'AgentIntegre',Agent)
    monkeypatch.setattr(s,'agent_transfere',transfert);monkeypatch.setattr(s,'empreintes',lambda *args:{})
    monkeypatch.setattr(s.sys,'stdin',io.StringIO('{"op":"auto","lots":3,"coups":1}\n{"op":"close"}\n'))
    args=SimpleNamespace(jeu=next(iter(s.AUTORISES)),sortie=tmp_path/'run',neuf=True,graine=0,
      prefixe=None,archives_niveaux=None,transfert_depuis=None,source=None)
    s.main(args)
    etat=json.loads((args.sortie/'etat.json').read_text())
    assert etat['statut']=='jeu_gagne' and etat['jeu_gagne']
    assert etat['coups_reels']==4 and etat['initialisations']==1
    assert len(instances)==2 and instances[0].env is instances[1].env
    assert len(transferts)==1 and np.array_equal(transferts[0],instances[0].image)
