import copy,pickle,json
from pathlib import Path
import numpy as np
import pytest
from chaine_agent_integree import AgentIntegre,canon
from preparer_modele_transfert import depuis_trace
from diagnostic_contexte_transfert import diagnostiquer,marqueurs
R=Path(__file__).parent
@pytest.fixture(scope='module')
def data():
 m,*_=depuis_trace(R/'runs/routage_arc1/reel/N1/partie',[1,2,3,4,5]);z=np.load(R/'runs/transfert_modele_commun_ar25_1/N2/partie.npz');return m,z

def agent(m,z):
 a=AgentIntegre([z['images'][0]],[],[],[],decouverte_courte=True,routage_classes=True);a.installer_modele_jeu(m);return a

def test_revision_locale_et_reprise_sans_reapprentissage(data):
 m,z=data;snapshot=pickle.dumps(m);a=agent(m,z);a.decider([1,2,3,4,5],secondes=2);a.observer(2,z['images'][1],z['film_1'],'continue')
 d=a.diagnostic_transfert
 assert d['contrat_candidat']=='selection_marqueur' and d['regles_conservees'] and d['plan_revoque']
 assert a.decider([1,2,3,4,5])['statut']=='experience_contrat_selection'
 o=a.observer(5,z['images'][2],z['film_2'],'continue')
 assert o['contexte_compatible'] and o['regles_reapprises']==0
 assert a.memoire_jeu is m and snapshot==pickle.dumps(m) and len(a.actions)==2
 assert a.debut_contexte==2 and len(a.chaines)==1
 # Reprise sans effacer la preuve de l'échec et sans rejouer le contexte invalidé.
 c=next(iter(a.chaines.values()));new=a._chaine(c.perception,c.programme)
 assert len(new.grilles)==1 and not new.lots and len(a.images)==3
 assert a.decider([1,2,3,4,5],secondes=2)['modeles']

def test_pas_de_selection_inventee_sur_deplacement_reel(data):
 m,z=data;a=agent(m,z);c=next(iter(a.chaines.values()))
 assert diagnostiquer(c,m,z['images'][2],z['images'][3],3) is None

def test_indices_absents_ne_sont_pas_certitude(data):
 m,z=data;a=agent(m,z);c=next(iter(a.chaines.values()));empty=copy.deepcopy(m);empty.contexte_selection={}
 assert diagnostiquer(c,empty,z['images'][0],z['images'][1],2) is None

def test_couleurs_marqueurs_non_codees():
 im=np.ones((9,9),dtype=int)*7;im[3,3]=2;im[5,5]=2
 assert marqueurs(im)=={2:{7:[(3,3),(5,5)]}}
 im[3,4]=6
 assert len(marqueurs(im)[2][7])==1

def test_aucune_commande_autorisee_aucune_action_inventee(data):
 m,z=data;a=agent(m,z);a.decider([1,2,3,4,5],secondes=2);a.observer(2,z['images'][1],z['film_1'],'continue')
 assert not a.decider([1,2,3,4])['actions']
