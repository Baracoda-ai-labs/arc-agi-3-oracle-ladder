"""Orientation dirigée d'une paire de pistes : relation de leurs centroïdes."""
import numpy as np
from chrysalide.arc3.objets_temps import Pisteur
class Direction:
 def __init__(self,ids):
  if len(ids)!=2:raise ValueError('Deux pistes synchrones nécessaires, relation ambiguë sinon')
  self.ids=sorted(ids);self.p=Pisteur(revisable=True,chevauche=True)
 def voir(self,im):
  obs=self.p.observer(im)
  if any(k not in obs for k in self.ids):return {}
  a,b=[np.mean(np.array(list(obs[k])),axis=0) for k in self.ids]
  d=b-a
  if np.linalg.norm(d)<.1:return {}
  return {0:int(round((np.arctan2(d[0],d[1])%(2*np.pi))/(np.pi/4)))%8}
