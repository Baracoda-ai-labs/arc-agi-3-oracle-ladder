"""Contrôle préfixé hors SDK : réparation sur deux transitions, suite jamais ajustée."""
import json,pickle,hashlib
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre,canon
from preparer_modele_transfert import depuis_trace
from diagnostic_contexte_transfert import compatible
R=Path(__file__).parent

def audit():
 source=R/'runs/routage_arc1/reel/N1/partie';p=R/'runs/transfert_modele_commun_ar25_1/N2/partie';z=np.load(p.with_suffix('.npz'));rows=json.loads(p.with_suffix('.json').read_text())['rows']
 m,*_=depuis_trace(source,[1,2,3,4,5]);initial=pickle.dumps(m)
 a=AgentIntegre([z['images'][0]],[],[],[],decouverte_courte=True,routage_classes=True);a.installer_modele_jeu(m)
 decisions=[]
 for i in range(2):
  d=a.decider([1,2,3,4,5],secondes=3);assert d['actions']==[rows[i]['action']]
  obs=a.observer(d['actions'][0],z['images'][i+1],z[f'film_{i+1}'],'continue')
  decisions.append({'coup':i+1,'decision':d['statut'],'action':d['actions'][0],'diagnostic':a.diagnostic_transfert,'observation_selection':obs if i else None})
 reserve=[]
 for i in range(16,len(rows)):
  im=z['images'][i];act=rows[i]['action']
  if not compatible(m,im):reserve.append({'coup':i+1,'statut':'contexte_hors_portee'});continue
  local=AgentIntegre([im],[],[],[],decouverte_courte=True)
  try:local.installer_modele_jeu(m)
  except ValueError as exc:
   reserve.append({'coup':i+1,'statut':'perception_non_extractible','raison':str(exc)});continue
  base=next(iter(local.chaines.values())).perception
  while hasattr(base,'base'):base=base.base
  if not isinstance(act,int) or any(ms.get(act,(0,0))==(0,0) for ms in base.mouvements.values()):
   reserve.append({'coup':i+1,'statut':'action_hors_modele_mouvement'});continue
  c=next(iter(local.chaines.values()));pred=local._predire(c,canon(act))
  if pred is None:reserve.append({'coup':i+1,'statut':'prediction_absente'});continue
  actual=c.perception.vue(z['images'][i+1]);diff=int(np.count_nonzero(np.asarray(pred['image'])!=actual))
  reserve.append({'coup':i+1,'statut':'conforme' if diff==0 else 'divergence','pixels_ecart':diff})
 assert initial==pickle.dumps(m)
 from collections import Counter
 return {'source_sha256':hashlib.sha256(source.with_suffix('.npz').read_bytes()).hexdigest(),'trace_sha256':hashlib.sha256(p.with_suffix('.npz').read_bytes()).hexdigest(),'correction_coups':[1,2],'inspection_diagnostic_coups':[1,16],'reserve_coups':[17,len(rows)],'decisions':decisions,'reserve':reserve,'resume':dict(Counter(x['statut'] for x in reserve)),'modele_source_inchange':True,'coups_sdk_nouveaux':0,'victoire_nouvelle':False}

if __name__=='__main__':
 report=audit();(R/'AUDIT_CONTEXTE_TRANSFERT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report['resume']))
