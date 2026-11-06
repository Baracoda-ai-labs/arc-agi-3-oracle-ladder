"""Transfert relatif par pixels ; profil issu de la théorie fantôme N1.
Aucun code du jeu lu. Les templates morphologiques sont des a priori explicites.
"""
import numpy as np,json,heapq,time
from collections import deque,Counter

def components(mask):
 seen=set();out=[]
 for y,x in zip(*np.where(mask)):
  p=(int(x),int(y))
  if p in seen:continue
  seen.add(p);q=[p];cs=set(q)
  while q:
   a,b=q.pop()
   for z in ((a-1,b),(a+1,b),(a,b-1),(a,b+1)):
    xx,yy=z
    if 0<=yy<mask.shape[0] and 0<=xx<mask.shape[1] and mask[yy,xx] and z not in seen:seen.add(z);cs.add(z);q.append(z)
  out.append(cs)
 return out

class MondeFantome:
 def __init__(self,before,after,action=1):
  # Couleur et empreinte du contrôlé déduites des pixels entrés/sortis.
  ys,xs=np.where(before[:62]!=after[:62]);changed=set(zip(map(int,xs),map(int,ys)))
  direction=((0,-1),(0,1),(-1,0),(1,0))[action-1]
  options=[]
  for color in sorted(set(int(after[y,x]) for x,y in changed)):
   for cs in components(after[:62]==color):
    if not (4<=len(cs)<=200) or not cs&changed or min(y for x,y in cs)<4:continue
    px=min(x for x,y in cs);py=min(y for x,y in cs)
    shape=frozenset((x-px,y-py) for x,y in cs)
    for distance in range(1,33):
     ox=px-direction[0]*distance;oy=py-direction[1]*distance
     oldcs={(ox+u,oy+v) for u,v in shape}
     if all(0<=x<64 and 4<=y<62 and before[y,x]==color for x,y in oldcs):
      evidence=len((cs^oldcs)&changed)
      options.append((evidence,len(cs),-distance,color,cs,oldcs));break
  if not options:raise ValueError('aucune translation rigide identifiable')
  _,_,_,self.color,shape,oldshape=max(options,key=lambda q:q[:4])
  self.pos=(min(x for x,y in shape),min(y for x,y in shape));self.shape=frozenset((x-self.pos[0],y-self.pos[1]) for x,y in shape)
  self.width=max(x for x,y in self.shape)+1;self.height=max(y for x,y in self.shape)+1
  self.start=(min(x for x,y in oldshape),min(y for x,y in oldshape))
  vacated=oldshape-shape
  self.floor=Counter(int(after[y,x]) for x,y in vacated).most_common(1)[0][0]
  self.step=abs(self.start[0]-self.pos[0])+abs(self.start[1]-self.pos[1]);assert self.step>0
  self.dirs=((0,-self.step),(0,self.step),(-self.step,0),(self.step,0))
  self.base=before.copy()
  for x,y in oldshape:self.base[y,x]=self.floor
  self.nodes=[]
  for y in range(self.start[1]%self.step,62-self.height+1,self.step):
   for x in range(self.start[0]%self.step,64-self.width+1,self.step):
    if all(self.base[y+v,x+u]!=0 for u,v in self.shape):self.nodes.append((x,y))
  self.node_set=set(self.nodes);self.groups=[];self.doors={};self.triggers={}
  for c in sorted(set(map(int,self.base[:62].flat))-{0,self.color,self.floor}):
   for cs in components(self.base[:62]==c):
    candidates=[]
    for pos in self.nodes:
     x,y=pos;n=sum((x+u,y+v) in cs for u,v in self.shape)
     if n>0:candidates.append((pos,n))
    if len(candidates)<2:continue
    # Porte = empreinte épaisse, dalle = petite tache contenue dans le nœud.
    maxn=max(n for pos,n in candidates)
    doors=[p for p,n in candidates if n==maxn];plates=[p for p,n in candidates if 1<n<maxn]
    if not doors or not plates:continue
    gid=len(self.groups);self.groups.append(dict(color=c,doors=doors,triggers=plates))
    for p in doors:self.doors[p]=gid
    for p in plates:self.triggers[p]=gid
  # Point isolé de la couleur du joueur, hors HUD, à atteindre par le centre.
  dots=[next(iter(c)) for c in components(self.base[:62]==self.color) if len(c)==1 and next(iter(c))[1]>3]
  self.goals={p for p in self.nodes if any(p[0]+self.width//2==x and p[1]+self.height//2==y for x,y in dots)}
  self.initial=(self.start,(),0,())
 def description(self):return dict(player_color=self.color,floor_color=self.floor,start=self.start,step=self.step,shape=sorted(self.shape),nodes=len(self.nodes),groups=self.groups,goals=sorted(self.goals))
