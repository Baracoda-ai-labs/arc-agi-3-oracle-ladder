"""Grammaire extensible et mémoire locale révocable, sans identité de jeu."""
from collections import deque
from loi_orientation import Lois

class Revision(Lois):
 def __init__(self,etages):
  super().__init__(etages[0]);self.etages=etages;self.niveaux={};self.revisions=[];self.confirmations=[]
 def candidats(self,a):
  es=self.exemples.get(str(a),[]);stage=self.niveaux.get(str(a),0)
  return [f for f in self.etages[stage] if all(f['valeurs'][b]==c for b,c in es)]
 def ajuster(self,a):
  k=str(a);es=self.exemples.get(k,[])
  if any(len({y for x,y in es if x==b})>1 for b,_ in es):
   self.revisions.append({'action':a,'statut':'representation_insuffisante','exemples':es.copy()});return False
  while not self.candidats(a) and self.niveaux.get(k,0)+1<len(self.etages):
   self.niveaux[k]=self.niveaux.get(k,0)+1
   self.revisions.append({'action':a,'statut':'grammaire_elargie','etage':self.niveaux[k]})
  return bool(self.candidats(a))
 def nouveau(self,a,state):
  return any(not any(x==b for x,y in self.exemples.get(str(a),[])) for b in state)
 def choix(self,state,offre):
  offre=sorted(a for a in offre if a in (1,2,3,4));q=deque([(tuple(state),[])]);vus={tuple(state)}
  while q:
   s,route=q.popleft();options=[]
   for a in offre:
    pred=[self.predire(a,b) for b in s]
    if any(not p for p in pred):continue
    if self.nouveau(a,s):options.append((sum(len(p)-1 for p in pred),-a,a))
   if options:
    a=max(options)[-1];return {'action':route[0] if route else a,'route':route+[a],'objectif':'experience_inedite','acces':bool(route)}
   if len(route)>=4:continue
   for a in offre:
    pred=[self.predire(a,b) for b in s]
    if pred and all(len(p)==1 for p in pred):
     nxt=tuple(p[0] for p in pred)
     if nxt not in vus:vus.add(nxt);q.append((nxt,route+[a]))
  return None
 def memoire(self):
  return {'statut':'provisoire','promotion_durable':False,'transferts_verifies':0,
          'portee':'orientation quantifiee modulo pi des pistes observees ; pas but/contact',
          'exemples':self.exemples,'etages':self.niveaux,'revisions':self.revisions,
          'confirmations_prospectives':self.confirmations,
          'regles':{str(a):self.candidats(a) for a in (1,2,3,4)}}
