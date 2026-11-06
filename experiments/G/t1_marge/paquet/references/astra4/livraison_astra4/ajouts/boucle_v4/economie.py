"""Fluent de jauge et espace de versions pour les coûts, depuis les pixels seuls.
Unité latente: coût d'une direction effective=1. Capacité entière 32..512.
Quantification floor/nearest/ceil; clic/espace 0..3; bloqué 0..1.
Le bootstrap utilise ces bornes de famille explicites, pas une garantie universelle.
"""
import numpy as np,json
from collections import Counter
class BudgetInconnu(RuntimeError):pass
class Economie:
 def __init__(self,image):
  self.rows=[];self.recharges=[];self.failures=[];self.initial=image.copy();self.valid=False
  candidates=[]
  for y in (0,1,62,63):
   color,n=Counter(map(int,image[y])).most_common(1)[0]
   adjacent=image[y-1 if y else 1]
   if n>=48 and np.sum(adjacent!=image[y])>=48:candidates.append((y,color,n))
  if not candidates:return
  self.y,self.color,self.width=max(candidates,key=lambda t:t[0]);self.columns=np.flatnonzero(image[self.y]==self.color);self.scale=64
  cap,q,click,space,blocked=np.meshgrid(np.arange(32,513),np.arange(3),np.arange(4),np.arange(4),np.arange(2),indexing='ij')
  self.cap=cap.ravel().astype(float);self.quant=q.ravel();self.click=click.ravel();self.space=space.ravel();self.blocked=blocked.ravel();self.lo=self.cap.copy();self.hi=self.cap.copy();self.alive=np.ones(len(self.cap),dtype=bool);self.valid=True;self.last=self.read(image);self.steps=0
 def read(self,image):return int(np.sum(image[self.y,self.columns]==self.color)) if self.valid else None
 def category(self,a,before=None,after=None):
  if isinstance(a,(tuple,list)):return 'clic'
  if a==5:return 'espace'
  # Category depends only on game area, including doors/ghosts; no-effect cost is separate.
  if before is not None and after is not None and np.array_equal(before[4:62],after[4:62]):return 'sans_effet'
  return 'direction'
 def costs(self,category):
  return self.click if category=='clic' else self.space if category=='espace' else self.blocked if category=='sans_effet' else np.ones_like(self.cap)
 def planned_cost(self,a):
  if isinstance(a,(tuple,list)):return self.click
  if a==5:return self.space
  return np.maximum(1,self.blocked)
 def admissible(self,actions):
  if not self.valid or not self.alive.any():return False
  total=sum((self.planned_cost(a) for a in actions),np.zeros_like(self.cap))
  # Strict margin: no sequence may end at depletion in any surviving theory.
  return bool(np.all((self.lo-total)[self.alive]>0))
 def cost_upper(self,actions):
  if not self.valid or not self.alive.any():return float('inf')
  return float(max(sum((self.planned_cost(a) for a in actions),np.zeros_like(self.cap))[self.alive]))
 def quantize(self,energy):
  x=np.maximum(0,energy)*self.scale/self.cap
  return np.minimum(self.width,np.where(self.quant==0,np.floor(x+1e-8),np.where(self.quant==1,np.floor(x+.5+1e-8),np.ceil(x-1e-8)))).astype(int)
 def update(self,a,before,after,terminal=False,won=False):
  if not self.valid:return
  obs=self.read(after);cat=self.category(a,before,after);cost=self.costs(cat);pl=self.lo-cost;ph=self.hi-cost;mask=self.alive
  low=self.quantize(pl);high=self.quantize(ph);bounds=[int(low[mask].min()),int(high[mask].max())] if mask.any() else None
  row=dict(step=self.steps+1,action=a,category=cat,observed_pixels=obs,predicted_pixels_interval=bounds,terminal=terminal,level_changed=won,versions_before=int(mask.sum()))
  self.steps+=1
  if won:
   row['excluded_reason']='nouveau_niveau';self.rows.append(row);return
  if obs>self.last:
   self.recharges.append(dict(step=self.steps,observed_gain_pixels=obs-self.last,action=a,status='hausse_observee_cause_inconnue'))
   # A recharge may depend on an unobserved condition. Reset energy interval, do not invent a rule.
   pl=np.zeros_like(pl);ph=self.cap.copy()
  # Invert quantizer to an energy interval, clipped at the image occlusion width.
  offslo=np.where(self.quant==0,0,np.where(self.quant==1,-.5,-1))
  offshi=np.where(self.quant==0,1,np.where(self.quant==1,.5,0))
  ol=(obs+offslo)*self.cap/self.scale;oh=(obs+offshi)*self.cap/self.scale
  ol=np.maximum(0,ol);oh=np.minimum(self.cap,oh)
  # Open interval endpoints must not admit an integer rounding boundary.
  ol+=np.where(self.quant==2,1e-7,0);oh-=np.where(self.quant!=2,1e-7,0)
  if obs==self.width:oh=self.cap.copy()
  if obs==0:ol=np.zeros_like(ol)
  self.lo=np.maximum(pl,ol);self.hi=np.minimum(ph,oh);self.alive&=self.lo<=self.hi+1e-9
  row['versions_after']=int(self.alive.sum());row['prediction_contains_observation']=bool(bounds and bounds[0]<=obs<=bounds[1])
  if terminal and not won:row['depletion_evidence']='compatible_epuisement' if obs==0 else 'autre_cause_ou_jauge_incomplete'
  if not self.alive.any():self.failures.append(dict(step=self.steps,reason='bareme_ou_jauge_hors_famille'));self.valid=False
  self.last=obs;self.rows.append(row)
 def report(self):
  result=dict(valid=self.valid,rows=self.rows,recharges=self.recharges,failures=self.failures,scope='barre_horizontale_de_bord; aucun OCR compteur; coûts relatifs; bootstrap famille bornée')
  if hasattr(self,'cap'):
   mask=self.alive
   result.update(row=self.y,color=self.color,visible_width=self.width,versions=int(mask.sum()),observed_pixels=self.last)
   if mask.any():
    result.update(capacity_interval=[float(self.cap[mask].min()),float(self.cap[mask].max())],remaining_interval=[float(self.lo[mask].min()),float(self.hi[mask].max())],costs={k:sorted(set(map(int,self.costs(k)[mask]))) for k in ('direction','sans_effet','clic','espace')})
  return result
 def save(self,path):
  from pathlib import Path
  Path(path).write_text(json.dumps(self.report(),indent=2))
