"""Séquence la moins chère dans l'arbre borné qui sépare des observations prédites.
Le risque est borné dans les hypothèses, pas prouvé pour une mécanique absente.
"""
import heapq

def signature(model,state):
 p,routes,idx,record,bits=state
 return p,tuple(sorted({r[min(idx,len(r)-1)] for r in routes})),tuple(sorted(model.opened(p,routes,idx,bits)))
def choisir(models,states,economy,maxdepth=3,forbidden=()):
 if len(models)<2:return None
 serial=0;heap=[(0,0,(),tuple(states))]
 while heap:
  cost,_,path,current=heapq.heappop(heap)
  if path:
   outcomes=[signature(m,s) for m,s in zip(models,current)]
   if len(set(outcomes))>1:return dict(actions=list(path),cost_upper=cost,outcomes=repr(outcomes),status='discriminante_dans_les_hypotheses')
  if len(path)>=maxdepth:continue
  for a in range(1,6):
   if not path and a in forbidden:continue
   seq=path+(a,)
   if not economy.admissible(seq):continue
   ns=tuple(m.step_state(s,a) for m,s in zip(models,current))
   if any(s is None for s in ns) or all(s==t for s,t in zip(current,ns)):continue
   serial+=1;heapq.heappush(heap,(economy.cost_upper(seq),serial,seq,ns))
 return None
