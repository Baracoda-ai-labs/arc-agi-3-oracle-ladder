"""Nombre et formes variables, objets et buts uniquement depuis les pixels.
Familles de couleurs/step/limite viennent du prior de mécanismes N4, sans scène.
"""
import numpy as np,time,heapq,itertools
from collections import Counter
from .transfert_fantome import components

def bitmask(ps):
 n=0
 for x,y in ps:
  if 0<=x<64 and 0<=y<64:n|=1<<(y*64+x)
 return n
class PousseeGenerale:
 def __init__(self,image,step=3,limit=15,colors=(11,14),controlled=14,solid=(15,),trav=(1,4,5,15),extension=(15,)):
  self.image0=image.copy();self.step_size=step;self.limit=limit;self.controlled=controlled;self.dirs=((0,-step),(0,step),(-step,0),(step,0))
  self.bg=2 # couleur du fond issue du prior de famille, jamais des coordonnées
  self.objects=[]
  for c in colors:
   for cs in components(image[:63]==c):
    if len(cs)<4:continue
    x=min(x for x,y in cs);y=min(y for x,y in cs);w=max(a for a,b in cs)-x+1;h=max(b for a,b in cs)-y+1
    self.objects.append(dict(color=c,shape=frozenset((a-x,b-y) for a,b in cs),start=(x,y),w=w,h=h))
  self.objects.sort(key=lambda o:(o['color'],o['start']))
  if not self.objects:raise ValueError('aucune_piece_percue')
  self.n=len(self.objects);self.selectable=[i for i,o in enumerate(self.objects) if o['color']==controlled]
  selected=[i for i in self.selectable if image[self.objects[i]['start'][1]+self.objects[i]['h']//2,self.objects[i]['start'][0]+self.objects[i]['w']//2]==0]
  if not selected:raise ValueError('selection_non_identifiee')
  self.targets=[]
  for cs in components(image[:63]==4):
   if len(cs)<8:continue
   x=min(x for x,y in cs);y=min(y for x,y in cs);w=max(a for a,b in cs)-x+1;h=max(b for a,b in cs)-y+1
   if w>=3 and h>=3:self.targets.append((2*x+w-1,2*y+h-1,w-2,h-2))
  self.target_options=[]
  for o in self.objects:
   self.target_options.append([j for j,t in enumerate(self.targets) if t[2:]==(o['w'],o['h'])])
  self.assignments=[]
  def assign(i,chosen):
   if i==self.n:self.assignments.append(tuple(chosen));return
   for j in self.target_options[i]:
    if j not in chosen:assign(i+1,chosen+[j])
  if self.n<=8:assign(0,[])
  support={(int(x),int(y)) for y,x in np.argwhere(image[:63]!=self.bg)}
  base=image.copy()
  for o in self.objects:
   x,y=o['start']
   for u in range(o['w']):
    for v in range(o['h']):support.add((x+u,y+v));base[y+v,x+u]=1
  self.base=base;supportmask=bitmask(support)
  self.solidmask=bitmask((int(x),int(y)) for y,x in np.argwhere(np.isin(base[:63],solid)))
  self.slidemask=bitmask((int(x),int(y)) for y,x in np.argwhere(~np.isin(base[:63],trav)))
  self.extensionmask=bitmask((int(x),int(y)) for y,x in np.argwhere(np.isin(base[:63],extension)))
  self.locs=[];self.fp=[];self.idx=[];self.normal=[];self.chains=[]
  for o in self.objects:
   loc=[];fp=[]
   for y in range(o['start'][1]%step,64-o['h'],step):
    for x in range(o['start'][0]%step,65-o['w'],step):
     mask=bitmask((x+u,y+v) for u,v in o['shape'])
     if mask&supportmask==mask:loc.append((x,y));fp.append(mask)
   idx={p:j for j,p in enumerate(loc)};normal={};chains={}
   for p,(x,y) in enumerate(loc):
    for a,(dx,dy) in enumerate(self.dirs):
     q=idx.get((x+dx,y+dy));normal[p,a]=q if q is not None and not fp[q]&self.solidmask else None
     chain=[]
     for k in range(1,64//step+1):
      q=idx.get((x+k*dx,y+k*dy))
      if q is None or fp[q]&self.slidemask:break
      chain.append(q)
      if k*step>=limit and not fp[q]&self.extensionmask:break
     chains[p,a]=chain
   self.locs.append(loc);self.fp.append(fp);self.idx.append(idx);self.normal.append(normal);self.chains.append(chains)
  self.start=tuple(self.idx[i][o['start']] for i,o in enumerate(self.objects))+(selected[0],)
  self.blocked=set()
 def step(self,s,a):
  if (s,a) in self.blocked:return s
  if a>=4:return s[:self.n]+(a-4,) if a-4 in self.selectable else s
  ps=list(s[:self.n]);sel=s[-1];x,y=self.locs[sel][ps[sel]];dx,dy=self.dirs[a];q=self.idx[sel].get((x+dx,y+dy))
  if q is None:return s
  hits=[j for j in range(self.n) if j!=sel and self.fp[sel][q]&self.fp[j][ps[j]]]
  if len(hits)==1:
   hit=hits[0];last=ps[hit]
   for r in self.chains[hit][ps[hit],a]:
    if any(self.fp[hit][r]&self.fp[j][ps[j]] for j in range(self.n) if j not in (hit,sel)):break
    last=r
   ps[hit]=last
  elif not hits and self.normal[sel][ps[sel],a] is not None:ps[sel]=q
  return tuple(ps)+(sel,)
 def h(self,s):
  centers=[(2*self.locs[i][s[i]][0]+o['w']-1,2*self.locs[i][s[i]][1]+o['h']-1) for i,o in enumerate(self.objects)]
  if not self.assignments:return 10000
  return min(sum((abs(centers[i][0]-self.targets[j][0])+abs(centers[i][1]-self.targets[j][1]))/(2*self.step_size) for i,j in enumerate(perm)) for perm in self.assignments)
 def solve(self,s=None,seconds=3,maxnodes=80000):
  s=s or self.start;t0=time.monotonic();heap=[(3*self.h(s),0,0,s)];best={s:0};parent={};n=0;serial=0
  if not self.assignments:return dict(status='BUT_NON_APPARIE',nodes=0)
  while heap and n<maxnodes and time.monotonic()-t0<seconds:
   _,g,_,cur=heapq.heappop(heap)
   if best.get(cur)!=g:continue
   if self.h(cur)==0:
    path=[]
    while cur in parent:old,a=parent[cur];path.append(a);cur=old
    return dict(status='SAT',actions=path[::-1],nodes=n)
   n+=1
   for a in list(range(4))+[4+i for i in self.selectable]:
    ns=self.step(cur,a)
    if ns==cur or g+1>=best.get(ns,10**9):continue
    best[ns]=g+1;parent[ns]=(cur,a);serial+=1
    heapq.heappush(heap,(g+1+3*self.h(ns),g+1,serial,ns))
  return dict(status='NO_PLAN_BOUNDED',nodes=n,seconds=time.monotonic()-t0)
 def concrete(self,s,a):
  if a<4:return a+1
  i=a-4;x,y=self.locs[i][s[i]];o=self.objects[i];return [6,x+o['w']//2,y+o['h']//2]
 def observe(self,image,pred):
  # Assignment allows color-preserving deformation of black direction cues.
  candidates=[]
  for i,o in enumerate(self.objects):
   vals=[]
   for p,(x,y) in enumerate(self.locs[i]):
    score=sum(image[y+v,x+u]==o['color'] for u,v in o['shape'])/len(o['shape'])
    if score>=.25 and (score>=.6 or (o['color']==self.controlled and image[y+o['h']//2,x+o['w']//2]==0)):
     distance=abs(x-self.locs[i][pred[i]][0])+abs(y-self.locs[i][pred[i]][1])
     vals.append((score,-distance,p))
   candidates.append(sorted(vals,reverse=True)[:8])
  best=None
  def search(i,ps,score):
   nonlocal best
   if i==self.n:
    if best is None or score>best[0]:best=(score,tuple(ps))
    return
   for confidence,dist,p in candidates[i]:
    if any(self.fp[i][p]&self.fp[j][ps[j]] for j in range(i)):continue
    search(i+1,ps+[p],score+confidence*len(self.objects[i]['shape'])+dist*.01)
  search(0,[],0)
  if best is None:return None
  ps=best[1];selected=[]
  for i in self.selectable:
   x,y=self.locs[i][ps[i]];o=self.objects[i]
   if image[y+o['h']//2,x+o['w']//2]==0:selected.append(i)
  return ps+(selected[0] if len(selected)==1 else pred[-1],)
 def describe(self):return dict(objects=[dict(color=o['color'],start=o['start'],width=o['w'],height=o['h'],pixels=len(o['shape'])) for o in self.objects],targets=self.targets,assignments=len(self.assignments),selectable=self.selectable,step=self.step_size,limit=self.limit)

 def matched(self,s):
  return {i for i,o in enumerate(self.objects) if any((2*self.locs[i][s[i]][0]+o['w']-1,2*self.locs[i][s[i]][1]+o['h']-1)==self.targets[j][:2] for j in self.target_options[i])}
 def subgoal(self,s,seconds=2,maxnodes=60000):
  """Recherche de palier: protéger les placements acquis au terme du sous-plan.
  Sous-buts lus dans l'appariement géométrique, jamais de coordonnées écrites.
  """
  placed=self.matched(s);t0=time.monotonic();best_result=None
  priorities=sorted(set(range(self.n))-placed,key=lambda i:(-len(self.objects[i]['shape']),i))
  for target in priorities:
   deadline=min(t0+seconds,time.monotonic()+seconds/max(1,len(priorities)))
   required=placed|{target}
   def h(cur):
    total=0
    for i in required:
     o=self.objects[i];x,y=self.locs[i][cur[i]];cx=2*x+o['w']-1;cy=2*y+o['h']-1
     total+=min((abs(cx-self.targets[j][0])+abs(cy-self.targets[j][1]))/(2*self.step_size) for j in self.target_options[i]) if self.target_options[i] else 10000
    return total
   heap=[(5*h(s),0,0,s)];best={s:0};parent={};serial=0;n=0
   while heap and n<maxnodes and time.monotonic()<deadline:
    _,g,_,cur=heapq.heappop(heap)
    if best.get(cur)!=g:continue
    if required<=self.matched(cur):
     path=[]
     while cur in parent:old,a=parent[cur];path.append(a);cur=old
     return dict(status='PALIER',actions=path[::-1],nodes=n,subgoal_object=target)
    n+=1
    for a in list(range(4))+[4+i for i in self.selectable]:
     ns=self.step(cur,a)
     if ns==cur or g+1>=best.get(ns,10**9):continue
     best[ns]=g+1;parent[ns]=(cur,a);serial+=1;heapq.heappush(heap,(g+1+5*h(ns),g+1,serial,ns))
  return dict(status='NO_SUBGOAL_BOUNDED',nodes=0)
