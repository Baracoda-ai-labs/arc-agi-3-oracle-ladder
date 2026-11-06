"""Orientation partielle, hypothèses exécutables issues de l'énumérateur officiel."""
import json
from pathlib import Path
import numpy as np
from chrysalide.arc3.objets_temps import Pisteur

class Orientation:
 def __init__(self):self.p=Pisteur(revisable=True,chevauche=True)
 def voir(self,im):
  out={}
  for k,cases in self.p.observer(im).items():
   xy=np.array(list(cases))
   if len(xy)<8 or len(xy)>400 or np.any(xy==0) or np.any(xy==63):continue
   vals,vec=np.linalg.eigh(np.cov(xy[:,::-1].T))
   if vals[-1]<1.25*max(vals[0],1e-6):continue
   v=vec[:,-1];angle=np.arctan2(v[1],v[0])%np.pi
   out[k]=int(round(angle/(np.pi/4)))%4
  return out

class Lois:
 def __init__(self,fonctions):self.fs=fonctions;self.exemples={}
 def ajouter(self,a,b,c):
  self.exemples.setdefault(str(a),[]).append((b,c))
 def candidats(self,a):
  es=self.exemples.get(str(a),[])
  return [f for f in self.fs if all(f['valeurs'][b]==c for b,c in es)]
 def predire(self,a,b):return sorted({f['valeurs'][b] for f in self.candidats(a)})
 def choisir(self,actuel,ids,offre):
  scores=[]
  for a in offre:
   if a not in (1,2,3,4):continue
   sorties=[self.predire(a,actuel[k]) for k in ids if k in actuel]
   if not sorties or any(not s for s in sorties):continue
   nouveau=sum(not any(b==actuel[k] for b,c in self.exemples.get(str(a),[])) for k in ids if k in actuel)
   scores.append((sum(len(s)-1 for s in sorties),nouveau,-a,a))
  return max(scores)[-1] if scores else None

def prefixe(base,fonctions,n=4):
 z=np.load(str(base)+'.npz');j=json.loads(Path(str(base)+'.json').read_text());acts=[r['action'] for r in j['rows'][:n]]
 o=Orientation();states=[o.voir(z['images'][0])]
 for i in range(n):
  for im in z[f'film_{i+1}']:s=o.voir(im)
  states.append(s)
 ids=set.intersection(*(set(s) for s in states));ids={k for k in ids if len({s[k] for s in states})>1}
 l=Lois(fonctions)
 for a,b,c in zip(acts,states,states[1:]):
  for k in ids:l.ajouter(a,b[k],c[k])
 return o,l,ids,states,z,j
