"""Sélection déterministe préinscrite : deux préfixes8, 10 sous-conditions chacun."""
import json
from pathlib import Path
from chaine_agent_integree import AgentIntegre
from dreamcoder_mots import taille
import numpy as np
R=Path(__file__).parent
out={'donneurs':[],'conditions':[]}
for dossier in ('perception_guidee_arc1','guidage_ka59_fige1'):
 p=R/'runs'/dossier/'N1/partie';z=np.load(p.with_suffix('.npz'));j=json.load(open(p.with_suffix('.json')))
 a=AgentIntegre(z['images'][:9],[r['action'] for r in j['rows'][:8],[z[f'film_{i+1}'] for i in range(8)],['continue']*8)
 a.reconstruire();nom,c=next(iter(a.chaines.items()))
 out['donneurs'].append({'archive':dossier,'prefixe':8,'modele':nom});vues=set();local=[]
 def walk(x):
  if isinstance(x,dict):
   for v in x.values():walk(v)
  elif isinstance(x,list):
   if x and x[0] in ('>=','<=','=','libre') and 5<=taille(x)<=24:
    sig=json.dumps(x,sort_keys=True)
    if sig not in vues and len(local)<10:vues.add(sig);local.append(x)
   for v in x:walk(v)
 walk(c.programme);out['conditions'].extend(local)
(R/'dreamcoder_conditions_donneurs.json').write_text(json.dumps(out,indent=2))
