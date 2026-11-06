from types import SimpleNamespace
import numpy as np
import pytest
from session_reprise_chaude import Relais

def test_relais_conserve_objet_sdk_et_budget_extensible(tmp_path):
 env=object();lab=SimpleNamespace(env=env,rows=[{}]*32,image=np.zeros((64,64),dtype=np.uint8),won=False,partie_gagnee=False)
 ctx={'lab':lab,'pool':[],'pistes':[1,2],'anciens':None,'l':SimpleNamespace(memoire=lambda:{'promotion_durable':False}),'o':None,'state':{0:5},'description':'relation_dirigee'}
 s=Relais(ctx,tmp_path/'relais');assert s.lab is lab and s.lab.env is env
 assert s.traiter({'op':'budget','coups_total':200})['budget_coups']==200
 assert s.traiter({'op':'status'})['coups_reels']==32
 assert len(lab.rows)==32
 with pytest.raises(ValueError):s.traiter({'op':'budget','coups_total':31})
 assert s.budget==200

def test_transition_conserve_sdk_memoire_et_compteurs(tmp_path):
 env=object()
 lab=SimpleNamespace(env=env,rows=[{}]*94,image=np.zeros((64,64),dtype=np.uint8),won=True,partie_gagnee=False,level=1,completed_baseline=0,output=tmp_path/'N1'/'partie')
 nxt=SimpleNamespace(env=env,rows=[],image=lab.image.copy(),won=False,partie_gagnee=False,level=2,completed_baseline=1)
 lab.next_level=lambda output:nxt
 memory=SimpleNamespace(memoire=lambda:{'provisoire':True})
 s=Relais(dict(lab=lab,pool=[],pistes=[1,2],anciens=None,l=memory,o=None,state={0:5},description='contenu_variable'),tmp_path/'relay')
 result=s.traiter({'op':'next_level'})
 assert s.lab.env is env and s.l is memory and s.precedents==[lab]
 assert result['coups_reels']==94 and result['coups_niveau']==0 and result['niveaux_gagnes']==1
 with pytest.raises(ValueError):s.traiter({'op':'budget','coups_total':93})
 with pytest.raises(ValueError):s.traiter({'op':'advance','coups':1})
 with pytest.raises(ValueError):s.traiter({'op':'next_level'})
 assert s.coups_totaux()==94
