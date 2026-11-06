"""Contre-exemples → réobservation intégrale ; jamais réparation de loi contradictoire."""
from loi_orientation import Orientation
from orientation_dirigee import Direction
from direction_contenu import DirectionContenu
from direction_contenu_variable import DirectionContenuVariable

def decrire(episodes,factory,ids):
 exemples={};supports={};conflits=[];manquants=[];dernier=None
 for ep,(images,actions,films) in enumerate(episodes):
  o=factory();avant=o.voir(images[0])
  for i,(a,film) in enumerate(zip(actions,films)):
   for frame in film:apres=o.voir(frame)
   for k in ids:
    if k not in avant or k not in apres:
     manquants.append((ep,i+1,k));continue
    key=(str(a),avant[k]);preuve={'episode':ep,'coup':i+1,'piste':k,'sortie':apres[k]}
    precedents=supports.setdefault(key,[])
    if any(p['sortie']!=apres[k] for p in precedents):conflits.append({'action':a,'etat':avant[k],'avant':precedents.copy(),'nouveau':preuve})
    precedents.append(preuve);exemples.setdefault(str(a),[]).append((avant[k],apres[k]))
   avant=apres
  dernier=avant
 return {'exemples':exemples,'conflits':conflits,'manquants':manquants,'dernier':dernier}

def reviser(episodes,pistes):
 candidats=[('axe_mod_pi',Orientation,sorted(pistes)),('relation_dirigee',lambda:Direction(pistes),[0]),('contenu_dans_contour',lambda:DirectionContenu(pistes),[0]),('contenu_variable',lambda:DirectionContenuVariable(pistes),[0])]
 journal=[]
 for nom,factory,ids in candidats:
  try:r=decrire(episodes,factory,ids)
  except (ValueError,KeyError) as e:
   journal.append({'representation':nom,'erreur':str(e)});continue
  journal.append({'representation':nom,'conflits':r['conflits'],'manquants':r['manquants']})
  if not r['conflits'] and not r['manquants']:
   return {'statut':'description_compatible','representation':nom,'ids':ids,'exemples':r['exemples'],'journal':journal,'promotion_durable':False}
 return {'statut':'perception_non_resolue','journal':journal,'promotion_durable':False}

def charger(base,n):
 import json
 from pathlib import Path
 import numpy as np
 z=np.load(str(base)+'.npz');j=json.loads(Path(str(base)+'.json').read_text())
 return (list(z['images'][:n+1]),[x['action'] for x in j['rows'][:n]],[z[f'film_{i+1}'] for i in range(n)])
