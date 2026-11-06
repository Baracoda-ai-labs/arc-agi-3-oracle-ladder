"""Réaffecter les rôles visuels ; conserver les tables causales du niveau appris."""
import numpy as np
from scipy.ndimage import label
from chrysalide.arc3.objets_temps import Pisteur
from direction_contenu_variable import DirectionContenuVariable
from apprendre_empreintes import chercher

def lier(modele,initial):
 old=modele['initial'];o=DirectionContenuVariable(modele['pistes']);assert o.voir(old)
 # Contour appris : même forme locale, translation autorisée ; pas d'identifiants persistants.
 def composantes(im):return Pisteur(revisable=True,chevauche=True).observer(im)
 old_obs=composantes(old);contours=[np.array(list(old_obs[k])) for k in modele['pistes'] if int(old[tuple(next(iter(old_obs[k])))])==o.couleur_contour];assert len(contours)==1
 ancien=contours[0];shape={tuple(p) for p in ancien-ancien.min(0)}
 obs=composantes(initial);matches=[]
 for k,pts in obs.items():
  pts=np.array(list(pts))
  if {tuple(p) for p in pts-pts.min(0)}==shape and int(initial[tuple(pts[0])])==o.couleur_contour:matches.append((k,pts))
 if len(matches)!=1:raise ValueError('Contour à réexaminer : correspondance ambiguë')
 k,pts=matches[0];lo=pts.min(0);hi=pts.max(0);contents=[]
 for j,vs in obs.items():
  pp=np.array(list(vs))
  if j!=k and np.all(pp.min(0)>=lo) and np.all(pp.max(0)<=hi):contents.append((len(pp),j))
 if not contents:raise ValueError('Contenu absent')
 ids={k,max(contents)[1]};delta=lo-ancien.min(0);x0,y0,x1,y1=modele['box'];dy,dx=map(int,delta);box=(x0+dx,y0+dy,x1+dx,y1+dy)
 # Gabarit de bouton provenant des clics ayant effectivement changé la couleur en N1.
 templates=[]
 for color,a in modele['selectors'].items():
  _,x,y=a;cc,n=label(old==color);idx=cc[y,x]
  if not idx:continue
  pp=np.argwhere(cc==idx);a0,b0=pp.min(0)-1;a1,b1=pp.max(0)+2
  if min(a0,b0)<0:continue
  patch=old[a0:a1,b0:b1];mask=np.ones(patch.shape,bool);mask[1:-1,1:-1]=False
  templates.append((patch,mask))
 selectors={}
 for patch,mask in templates:
  h,w=patch.shape
  for y in range(initial.shape[0]-h+1):
   for x in range(initial.shape[1]-w+1):
    v=initial[y:y+h,x:x+w]
    if np.array_equal(v[mask],patch[mask]) and len(np.unique(v[1:-1,1:-1]))==1:
     c=int(v[1,1]);selectors[c]=['clic',x+w//2,y+h//2]
 if not selectors:raise ValueError('Sélecteurs à réexaminer')
 return dict(pistes=ids,box=box,selectors=selectors,initial=initial)

def observer(binding,images,films):
 o=DirectionContenuVariable(binding['pistes']);s=o.voir(images[0])
 for film in films:
  for frame in film:s=o.voir(frame)
 if 0 not in s:raise ValueError('Perception incomplète')
 im=images[-1];x0,y0,x1,y1=binding['box']
 return (im,s[0],o.couleur),dict(phase=s[0],color=o.couleur,canvas=im[y0:y1,x0:x1].tolist())

def planifier(modele,binding,images,films):
 current,etat=observer(binding,images,films);im=binding['initial'];x0,y0,x1,y1=binding['box'];h=y1-y0;w=x1-x0;goals=[]
 palette=set(binding['selectors'])
 for y in range(im.shape[0]-h+1):
  for x in range(im.shape[1]-w+1):
   if not(x+w<=x0 or x>=x1 or y+h<=y0 or y>=y1):continue
   g=im[y:y+h,x:x+w]
   if len(np.unique(g))<2 or not set(np.unique(g))<=palette:continue
   if not all(np.array_equal(a[y:y+h,x:x+w],g) for a in images):continue
   if not any(np.array_equal(g,other) for other in goals):goals.append(g.copy())
 report=dict(etat_observe=etat,modeles_visuels_candidats=len(goals),selecteurs=binding['selectors'],region=binding['box'],regles_reapprises=0,portee='transfert_provisoire')
 if len(goals)!=1:return report,None
 return chercher(current,binding['box'],modele['rules'],binding['selectors'],modele['nav'],goals,report)
