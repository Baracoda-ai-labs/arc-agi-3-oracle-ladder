"""Raccorder l'induction existante de prolongation aux supports suivis observés."""
import copy
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.logique.induction import _glisse
from chrysalide.arc3.moteur import _composantes
from glissade_distance_observee import apprendre,compiler
from transfert_roles import RolesReaffectes
from memoire_reparations_roles import conserver

def recolter(c,k):
 pousses=[]
 z=Chaine(c.perception,c.programme,c.grilles[:1],[],c.actions);_,(pc,sc)=z.rejouer()
 for t,lot in enumerate(c.lots):
  if len(lot['actions'])!=1:continue
  ancien=copy.deepcopy(sc);pc.step(sc,c.action_tuple(lot['actions'][0]));obs=_composantes(c.perception.vue(c.grilles[t+1]),c.perception.fond)
  e0=[]
  for q in ancien.sprites:
   cols=set(np.unique(q['pixels']))-{-1}
   if len(cols)!=1:continue
   col=int(next(iter(cols)));ys,xs=np.where(q['pixels']>=0);forme=frozenset(zip(xs.tolist(),ys.tolist()));e0.append((col,forme,q['x'],q['y']))
  for q in e0:
   anciens_meme={r[2:] for r in e0 if r[:2]==q[:2]}
   nouveaux=[r for r in obs if r[:2]==q[:2] and r[2:] not in anciens_meme]
   if any(r[:2]==q[:2] and r[2:]==q[2:] for r in obs):continue
   matches=nouveaux
   if len(matches)!=1 or matches[0][2:]==q[2:]:continue
   dx,dy=matches[0][2]-q[2],matches[0][3]-q[3]
   if bool(dx)==bool(dy) or abs(dx)+abs(dy)<=3:continue
   # Only existing non-controlled pushed supports, never background pieces.
   if not any(o['x']==q[2] and o['y']==q[3] and 'bloqueur' in o.get('tags',[]) and set(np.unique(o['pixels']))-{-1}=={q[0]} for o in ancien.sprites):continue
   pousses.append((k,t,q,matches[0],e0))
 return pousses


def proposer(source,precedents):
 diag={'admis':False,'provisoire':True,'but_change':False,'brique':'induction._glisse/export_langage._glisse'}
 if type(source.perception) is not RolesReaffectes:return None,{**diag,'refus':'representation_non_applicable'}
 if getattr(source.perception,'prolongation_glisse_observee',None):return None,{**diag,'refus':'prolongation_deja_etayee'}
 try:classe,base,preuves_base=apprendre(source.perception,precedents)
 except (ValueError,KeyError,TypeError,IndexError) as e:return None,{**diag,'refus':str(e)}
 sources=[];ancien=getattr(source,'modele_source_transfert',None)
 while ancien is not None:sources.append(ancien);ancien=getattr(ancien,'modele_source_transfert',None)
 sources=list(reversed(sources))+[source]
 pousses=[]
 for k,c in enumerate(sources):pousses.extend(recolter(c,k))
 g=_glisse(pousses)
 if not g or g[0]!=base[0] or not g[4]:return None,{**diag,'refus':'prolongation_non_etablie'}
 ancienne=(base[0],base[1],base[2]|g[2],base[3],base[4])
 nouvelle=(base[0],base[1]|g[1],ancienne[2],g[3],g[4])
 def remplacer(c,param,verifier=False):
  p=copy.deepcopy(c.programme)
  noms={r['nom'] for r in p['regles'] if r['nom'].startswith('glissade ') or r['nom']=='sélecteur observé pour glissade'}
  base_p=copy.deepcopy(p);base_p['regles']=[r for r in base_p['regles'] if r['nom'] not in noms]
  export=compiler(c.perception,base_p,classe,param)
  remp={r['nom']:r for r in export['regles'] if r['nom'] in noms}
  if verifier:return remp=={r['nom']:r for r in p['regles'] if r['nom'] in noms}
  p['regles']=[remp.get(r['nom'],r) for r in p['regles']];return p
 if not remplacer(source,ancienne,True):return None,{**diag,'refus':'glissade_source_hors_contrat'}
 controles=[];candidat=None
 for s in sources:
  p=remplacer(s,nouvelle);v=copy.deepcopy(s.perception);v.programme_transfere=copy.deepcopy(p)
  c=Chaine(v,p,s.grilles,s.lots,s.actions,coups_deja_joues=s.coups,reserve=s.limite,
           films=[e['images'] if e else None for e in s.films.entrees])
  ctrl,etat=c.rejouer();controles.append(ctrl)
  if etat is None:return None,{**diag,'refus':'contre_exemple','controles':controles}
  candidat=c
 conserver(source,candidat);candidat.activer_atms()
 preuve={'base':g[0],'classes_prolongeantes':sorted(g[4]),'poussees':[{'source':k,'transition':t+1,'classe':a[0],
    'depart':list(a[2:]),'arrivee':list(b[2:])} for k,t,a,b,_ in pousses]}
 candidat.perception.prolongation_glisse_observee=preuve
 candidat.revision_locale={'operateur':'prolongation_glisse_existante','generalisation':False}
 return candidat,{**diag,'admis':True,'preuve':preuve,'controles':controles}
