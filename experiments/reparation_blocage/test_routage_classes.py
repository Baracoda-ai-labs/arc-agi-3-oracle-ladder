import json,time
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre
R=Path(__file__).parent
CASES={'ar25':'perception_guidee_arc1/N1','ka59':'guidage_ka59_fige1/N1',
'm0r0':'identites_commun_m0r0_1/reel/N1','cd82':'transfert_commun_cd82_1/reel/N1'}

def charger(nom,active):
 p=R/'runs'/CASES[nom]/'partie';j=json.loads(p.with_suffix('.json').read_text());z=np.load(p.with_suffix('.npz'))
 acts=j.get('actions') or [x['action'] for x in j['rows']]
 return AgentIntegre(z['images'][:9],acts[:8],[z[f'film_{i+1}'] for i in range(8)],['continue']*8,
                     decouverte_courte=True,routage_classes=active)

def test_comparaison_quatre_prefixes():
 result={}
 for nom in CASES:
  result[nom]={}
  for flag in (False,True):
   a=charger(nom,flag);t=time.monotonic();d=a.decider([1,2,3,4,6],secondes=4)
   result[nom][str(flag)]={'secondes':round(time.monotonic()-t,3),'actions':d['actions'],
     'modeles':list(a.chaines),'refus':sum(j['type']=='capacite_non_applicable' for j in a.journal),
     'differees':a.capacites_differees,'reouverture':a.routage_exhaustif}
   if flag:
    trace=[j for j in a.journal if j['type']=='routage_ontologie'];assert trace
    assert trace[0]['droit_action'] is False and trace[0]['catalogue_complet_conserve']
  assert result[nom]['False']['actions']==result[nom]['True']['actions']
 print(json.dumps(result,ensure_ascii=False))
 assert any(result[n]['True']['differees'] for n in result)


def test_refus_plan_reouvre_catalogue(monkeypatch):
 from chaine_coherente import Chaine
 monkeypatch.setattr(Chaine,'proposer',lambda *a,**k:{'statut':'aucun_plan'})
 a=charger('ar25',True);a.decider([1,2,3,4,6],secondes=2)
 assert a.routage_exhaustif and not a.capacites_differees
 assert any(j.get('raison')=='aucun_plan_admis' for j in a.journal)


def test_divergence_reouvre_catalogue(monkeypatch):
 a=charger('ar25',True);a.reparation=False;d=a.decider([1,2,3,4,6])
 assert a.capacites_differees
 for c in a.chaines.values():
  monkeypatch.setattr(c,'observer',lambda *args,**kw:{'statut':'divergence'})
 im=a.images[-1].copy();a.observer(d['actions'][0],im,[im],'continue')
 assert a.routage_exhaustif and a.reconstruction and not a.capacites_differees
