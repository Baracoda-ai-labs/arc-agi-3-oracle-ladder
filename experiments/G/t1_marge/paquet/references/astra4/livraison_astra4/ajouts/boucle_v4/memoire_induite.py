"""Espace de versions mémoire/cadence, observation des fantômes couleur du prior.
Aucune vérité moteur: poses contrôlées et pixels visibles seulement.
"""
from .contrats_v4 import ajouter_memoire
import numpy as np
class MemoireInduite:
 def __init__(self,model,capacity_hint,ghost_color=2):
  self.start=model.start;self.shape=model.shape;self.ghost_color=ghost_color;self.hint=capacity_hint
  self.hypotheses=[dict(capacity=k,policy=p,clock=c,routes=(),record=(),idx=0,player=self.start,errors=0) for k in range(1,9) for p in ('clear','fifo') for c in ('effective','all')];self.rows=[]
 def update(self,action,player,image):
  actual={(int(x),int(y)) for y,x in np.argwhere(image[7:62]==self.ghost_color)}
  actual={(x,y+7) for x,y in actual}
  occupied={(player[0]+u,player[1]+v) for u,v in self.shape}
  actual-=occupied
  for h in self.hypotheses:
   if action==5:
    if h['record']:h['routes']=ajouter_memoire(h['routes'],(self.start,)+h['record'],h['capacity'],h['policy'])
    h['record']=();h['idx']=0
   elif action in (1,2,3,4):
    if player!=h['player'] or h['clock']=='all':
     if h['routes']:h['idx']=min(h['idx']+1,max(map(len,h['routes']))-1)
     h['record']+=(player,)
   h['player']=player
   expected=set()
   for route in h['routes']:
    p=route[min(h['idx'],len(route)-1)];expected|={(p[0]+u,p[1]+v) for u,v in self.shape}
   expected-=occupied
   h['errors']+=len(expected^actual)
  valid=[h for h in self.hypotheses if h['errors']==0]
  self.rows.append(dict(action=action,valid_versions=len(valid),min_pixel_errors=min(h['errors'] for h in self.hypotheses)))
  if not valid:return None
  return min(valid,key=lambda h:(abs(h['capacity']-self.hint),h['clock']!='effective',h['policy']!='clear',h['capacity']))
 def report(self):
  return dict(valid=[{k:h[k] for k in ('capacity','policy','clock')} for h in self.hypotheses if h['errors']==0],rows=self.rows,scope='positions absolues mémorisées; couleur fantôme du prior; pas de preuve si toutes variantes rejetées')
