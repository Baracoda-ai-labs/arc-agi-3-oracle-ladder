"""Profil de mémoire variable, géométrie et liens calculés sur l'image.
Hors logique: rendu et recherche; mécanismes purs séparés dans contrats_v4.
"""
from .transfert_fantome import MondeFantome,components
from collections import deque
import time,heapq,itertools,numpy as np

class FantomeGeneral(MondeFantome):
 def __init__(self,before,after,action,capacity=2,overflow='clear',reset_bits=True):
  super().__init__(before,after,action)
  slots=[c for c in components(before[:7]==1) if len(c)==9]
  self.capacity=len(slots) if slots else capacity;self.capacity_hint=self.capacity;self.overflow=overflow;self.reset_bits=reset_bits
  self.nodes=[]
  cx=self.width//2;cy=self.height//2
  for y in range(self.start[1]%self.step,62-self.height+1,self.step):
   for x in range(self.start[0]%self.step,64-self.width+1,self.step):
    if all(self.base[y+v,x+u]!=0 for u,v in self.shape):self.nodes.append((x,y))
  self.node_set=set(self.nodes);self.groups=[];self.doors={};self.triggers={}
  for c in sorted(set(map(int,self.base[:62].flat))-{0,self.color,self.floor}):
   for cs in components(self.base[:62]==c):
    ds=[];ts=[];hollow=[]
    for x,y in self.nodes:
     inside=sum((x+u,y+v) in cs for u,v in self.shape)
     outer={(x+u,y+v) for u in range(-1,self.width+1) for v in range(-1,self.height+1) if u in (-1,self.width) or v in (-1,self.height)}
     outside=len(outer&cs)
     center={(x+cx+u,y+cy+v) for u in (-1,0,1) for v in (-1,0,1)}
     if inside>=len(self.shape)*.7:ds.append((x,y))
     elif outside>=len(outer)*.65:ds.append((x,y));hollow.append((x,y))
     elif len(center&cs)>=8:ts.append((x,y))
    if ds and ts:
     gid=len(self.groups);kind='portal' if hollow else ('toggle' if c==11 else 'held')
     self.groups.append(dict(color=c,doors=ds,triggers=ts,kind=kind,initial_open=bool(hollow)))
     for p in ds:self.doors[p]=gid
     for p in ts:self.triggers[p]=gid
  dots=[next(iter(c)) for c in components(self.base[:62]==self.color) if len(c)==1 and next(iter(c))[1]>3]
  self.goals={p for p in self.nodes if (p[0]+cx,p[1]+cy) in dots}
  self.initial=(self.start,(),0,(),0)
 def occupants(self,p,routes,idx):return {p}|{r[min(idx,len(r)-1)] for r in routes}
 def opened(self,p,routes,idx,bits=0):
  occ=self.occupants(p,routes,idx);out=set()
  for g,group in enumerate(self.groups):
   occupied=any(t in occ for t in group['triggers'])
   kind=group['kind']
   from .contrats_v4 import porte
   if kind=='portal' or porte(kind,occupied,bool(bits&(1<<g))):out.add(g)
  return out
 def step_state(self,s,a):
  from .contrats_v4 import ajouter_memoire
  p,routes,idx,record,bits=s
  if a==5:
   rs=ajouter_memoire(routes,(self.start,)+record,self.capacity,self.overflow) if record else routes
   return self.start,rs,0,(),(0 if self.reset_bits else bits)
  if (p,a) in getattr(self,"blocked",set()):return s
  dx,dy=self.dirs[a-1];q=p[0]+dx,p[1]+dy
  if q not in self.node_set or q in self.doors and self.doors[q] not in self.opened(p,routes,idx,bits):return s
  ni=min(idx+1,max(map(len,routes))-1) if routes else 0
  before=self.occupants(p,routes,idx);after=self.occupants(q,routes,ni)
  for g,group in enumerate(self.groups):
   if group['kind']=='toggle' and any(t in after for t in group['triggers']) and not any(t in before for t in group['triggers']):bits^=1<<g
  if q in self.doors and self.doors[q] not in self.opened(q,routes,ni,bits):return None
  for group in self.groups:
   if group['kind']=='portal' and q in group['doors'] and any(t in after for t in group['triggers']):
    ds=group['doors'];q=ds[(ds.index(q)+1)%len(ds)]
  return q,routes,ni,record+(q,),bits
 def nav(self,s,target,maxsteps=100):
  todo=deque([(s,())]);seen={(s[0],s[2],s[4])}
  while todo:
   cur,path=todo.popleft()
   if cur[0]==target:return cur,list(path)
   if len(path)>=maxsteps:continue
   for a in range(1,5):
    ns=self.step_state(cur,a)
    if ns is None:continue
    key=ns[0],ns[2],ns[4]
    if key not in seen:seen.add(key);todo.append((ns,path+(a,)))
  return None
 def solve(self,s=None,seconds=2,maxmacros=5,maxnodes=5000):
  s=s or self.initial;t0=time.monotonic();heap=[(0,0,s,[])];seen=set();serial=0
  targets=set(self.triggers)|self.goals
  for p,g in self.triggers.items():
   if self.groups[g]['kind']=='toggle':
    for dx,dy in self.dirs:
     q=p[0]+dx,p[1]+dy
     if q in self.node_set:targets.add(q)
  while heap and time.monotonic()-t0<seconds and len(seen)<maxnodes:
   _,_,cur,path=heapq.heappop(heap)
   key=cur[0],cur[1],cur[2],cur[4],cur[3] # future memory depends on whole record
   if key in seen:continue
   seen.add(key)
   if cur[0] in self.goals:return dict(status='SAT',actions=path,nodes=len(seen))
   if len(path)>140 or path.count(5)>maxmacros:continue
   for target in sorted(targets):
    r=self.nav(cur,target)
    if r is None:continue
    nxt,acts=r
    if target in self.goals:return dict(status='SAT',actions=path+acts,nodes=len(seen))
    if not acts:continue
    successors=[(nxt,acts)]
    if target in self.triggers and self.groups[self.triggers[target]]['kind']=='held':successors=[(self.step_state(nxt,5),acts+[5])]
    for ns,aa in successors:
     serial+=1;covered={r[-1] for r in ns[1]}
     remaining=sum(p not in covered for p,g in self.triggers.items() if self.groups[g]['kind'] in ('held','portal'))
     dist=min((abs(ns[0][0]-g[0])+abs(ns[0][1]-g[1]))/self.step for g in self.goals) if self.goals else 0
     priority=len(path)+len(aa)+30*remaining+dist+10*sum(not(ns[4]&(1<<g)) for g,q in enumerate(self.groups) if q['kind']=='toggle')
     heapq.heappush(heap,(priority,serial,ns,path+aa))
  return dict(status='NO_PLAN_BOUNDED',nodes=len(seen),seconds=time.monotonic()-t0)
 def observe_player(self,image,pred):
  candidates=[]
  for p in self.nodes:
   n=sum(image[p[1]+v,p[0]+u]==self.color for u,v in self.shape)
   if n>=len(self.shape)*.8:candidates.append((n,-abs(p[0]-pred[0])-abs(p[1]-pred[1]),p))
  return max(candidates)[2] if candidates else None
 def describe(self):return dict(**self.description(),capacity=self.capacity,overflow=self.overflow,reset_bits=self.reset_bits)
