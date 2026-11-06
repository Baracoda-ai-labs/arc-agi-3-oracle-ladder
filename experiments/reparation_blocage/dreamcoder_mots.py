"""Macros apprises figées ; admission par expansion exacte, aucune invention locale."""
import copy, hashlib,json
from pathlib import Path
from chrysalide.arc3.langage import Programme

def taille(x):
 return 1+sum(taille(v) for v in x) if isinstance(x,list) else 1

def substituer(x,env):
 if isinstance(x,str) and x in env:return copy.deepcopy(env[x])
 if isinstance(x,list):return [substituer(v,env) for v in x]
 if isinstance(x,dict):return {k:substituer(v,env) for k,v in x.items()}
 return x

def correspond(pattern,x,params,env):
 if isinstance(pattern,str) and pattern in params:
  # Arguments atomiques seulement : ne pas modifier évaluation paresseuse des conditions.
  if isinstance(x,(list,dict)):return False
  if pattern in env:return env[pattern]==x
  env[pattern]=x;return True
 if type(pattern)!=type(x):return False
 if isinstance(pattern,list):return len(pattern)==len(x) and all(correspond(a,b,params,env) for a,b in zip(pattern,x))
 return pattern==x

def appliquer(programme,bibliotheque):
 original=copy.deepcopy(programme);defs=bibliotheque['mots'];utilises=set();compteurs={'appels':0}
 def rec(x):
  if isinstance(x,dict):return {k:rec(v) for k,v in x.items()}
  if not isinstance(x,list):return x
  for nom,d in defs.items():
   env={}
   if correspond(d['corps'],x,d['params'],env) and set(env)==set(d['params']):
    appel=[nom]+[env[p] for p in d['params']]
    if taille(appel)<taille(x):
     utilises.add(nom);compteurs['appels']+=1;return appel
  return [rec(v) for v in x]
 nouveau=rec(original)
 if set(original.get('mots',{}))&set(defs):raise ValueError('Collision mots')
 nouveau['mots']={**original.get('mots',{}),**{k:defs[k] for k in sorted(utilises)}}
 def expand(x):
  if isinstance(x,list):
   if x and isinstance(x[0],str) and x[0] in utilises:
    d=defs[x[0]];return substituer(d['corps'],dict(zip(d['params'],x[1:],strict=True)))
   return [expand(v) for v in x]
  if isinstance(x,dict):return {k:expand(v) for k,v in x.items()}
  return x
 rendu=expand({k:v for k,v in nouveau.items() if k!='mots'})
 attendu={k:v for k,v in original.items() if k!='mots'}
 if rendu!=attendu:raise ValueError('Expansion différente')
 Programme(nouveau)
 return nouveau,{'mots_utilises':sorted(utilises),'expansion_exacte':True,
   'appels_macros':compteurs['appels'],'noeuds_total_avant':taille_arbre(original),'noeuds_total_apres':taille_arbre(nouveau),
   'noeuds_avant':taille_arbre(attendu),'noeuds_apres':taille_arbre({k:v for k,v in nouveau.items() if k!='mots'}),
   'bibliotheque_sha256':hashlib.sha256(json.dumps(bibliotheque,sort_keys=True).encode()).hexdigest()}

def taille_arbre(x):
 if isinstance(x,dict):return 1+sum(taille_arbre(v) for v in x.values())
 if isinstance(x,list):return 1+sum(taille_arbre(v) for v in x)
 return 1
