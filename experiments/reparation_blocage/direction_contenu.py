"""Réacquisition du contenu dans un contour, sans identité persistante du contenu."""
import numpy as np
from chrysalide.arc3.objets_temps import Pisteur
class DirectionContenu:
 def __init__(self,ids):self.ids=sorted(ids);self.p=Pisteur(revisable=True,chevauche=True);self.ancre=None;self.couleurs=None
 def voir(self,im):
  im=np.asarray(im);obs=self.p.observer(im)
  if self.ancre is None:
   if len(self.ids)!=2 or any(k not in obs for k in self.ids):return {}
   for a,b in (self.ids,self.ids[::-1]):
    aa=np.array(list(obs[a]));bb=np.array(list(obs[b]));lo=aa.min(0);hi=aa.max(0)
    if np.all(bb.min(0)>=lo) and np.all(bb.max(0)<=hi):
     self.ancre=a;self.couleurs=set(int(im[y,x]) for y,x in bb);break
   if self.ancre is None:return {}
  if self.ancre not in obs:return {}
  aa=np.array(list(obs[self.ancre]));lo=aa.min(0);hi=aa.max(0);region=im[lo[0]:hi[0]+1,lo[1]:hi[1]+1]
  bb=np.argwhere(np.isin(region,list(self.couleurs)))+lo
  if len(bb)<3:return {}
  d=bb.mean(0)-aa.mean(0)
  if np.linalg.norm(d)<.1:return {}
  return {0:int(round((np.arctan2(d[0],d[1])%(2*np.pi))/(np.pi/4)))%8}
