from pathlib import Path
import json,pickle
import numpy as np
import pytest
from chaine_agent_integree import AgentIntegre
from preparer_modele_transfert import depuis_trace
from modele_jeu import ModeleJeu
from apprendre_empreintes import apprendre
from loi_orientation import prefixe
R=Path(__file__).parent

@pytest.fixture(scope='module')
def acquis_objets():
 return depuis_trace(R/'runs/routage_arc1/reel/N1/partie',[1,2,3,4,5])

def test_objets_formes_nouvelles_mouvements_conserves(acquis_objets):
 m,actions,images,_=acquis_objets;sha=pickle.dumps(m)
 a=AgentIntegre([images[-1]],[],[],[],decouverte_courte=True,routage_classes=True);a.installer_modele_jeu(m)
 d=a.decider([1,2,3,4,5],secondes=3)
 assert d['actions'] and a.memoire_jeu is m and sha==pickle.dumps(m)
 old=m.acquis[0];new=next(iter(a.chaines.values())).perception
 while hasattr(old,'base'):old=old.base
 while hasattr(new,'base'):new=new.base
 assert old.mouvements==new.mouvements and old.mobiles[0].shape!=new.mobiles[0].shape
 assert not a.actions and not a.reconstruction

def test_empreintes_chaine_commune_rejoue_transfert_verifie():
 base=R/'runs/transfert_commun_cd82_1/reel/N1/partie';_,_,ids,_,_,_=prefixe(base,[])
 m=ModeleJeu('empreintes',apprendre([base,R/'runs/session_perception_arc1/N1/partie'],ids,exporter=True),{'source':'filmsN1'})
 b=R/'runs/session_perception_arc1/N2/partie';z=np.load(b.with_suffix('.npz'));rows=json.loads(b.with_suffix('.json').read_text())['rows']
 a=AgentIntegre([z['images'][0]],[],[],[],decouverte_courte=True);a.installer_modele_jeu(m)
 for i,row in enumerate(rows):
  d=a.decider([1,2,3,4,5,6]);assert d['actions']==[row['action']]
  outcome=a.observer(row['action'],z['images'][i+1],z[f'film_{i+1}'],'niveau' if i==len(rows)-1 else 'continue')
  assert outcome['conforme']
 assert len(a.actions)==6

def test_contradiction_retour_perception():
 m=ModeleJeu('empreintes',{},{});a=AgentIntegre([np.zeros((64,64),dtype=int)],[],[],[])
 a.transfert_empreintes=({},{});a.attente={'actions':[1],'rapport':{'prediction_prochain_coup':{}}}
 # Le contrôle d'observation est testé avec un observateur substitué, sans oracle de jeu.
 from unittest.mock import patch
 with patch('transfert_empreintes.observer',return_value=(None,{'phase':3})):
  r=a.observer(1,np.ones((64,64),dtype=int),[np.ones((64,64),dtype=int)],'continue')
 assert not r['conforme'] and a.reconstruction and a.transfert_empreintes is None


@pytest.mark.parametrize('changement', ['regle', 'but'])
def test_programme_hors_contrat_refuse_sans_mutation(acquis_objets, changement):
 import copy
 m,_,images,_=acquis_objets
 m=copy.deepcopy(m)
 if changement=='regle':
  m.acquis[1]['regles'].append({'nom':'loi_contact_apprise','phase':2,'quand':True,'alors':[]})
 else:
  terminale=next(r for r in m.acquis[1]['regles'] if r['nom']=='but_correspondance_hypothese')
  terminale['quand']=False
 a=AgentIntegre([images[-1]],[],[],[]);a.commandes_connues={7}
 avant=pickle.dumps(m); journal=copy.deepcopy(a.journal)
 with pytest.raises(ValueError,match='Programme acquis non réaffectable'):
  a.installer_modele_jeu(m)
 assert a.memoire_jeu is None and a.commandes_connues=={7} and not a.chaines
 assert a.journal==journal and pickle.dumps(m)==avant
