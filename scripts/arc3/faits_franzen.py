"""Constats sur images finales du journal Franzen, sans interpréter les films absents.

Ce module est hors runtime ; il n'effectue ni E/S ni inférence ni appel SDK.
"""
from collections import defaultdict
import re

HEADER='OBSERVED FINAL FRAMES (current life only; animations not available):\n'

def faits_finaux(histoire, courant, minimum=2, max_bytes=600):
 if courant is None or not histoire:return ''
 if minimum<1 or max_bytes<0:raise ValueError('bornes invalides')
 dernier=histoire[-1].frame
 if dernier is None or dernier.level!=courant.level or dernier.step!=courant.step or dernier.grid!=courant.grid:return ''
 # Début après la dernière frontière connue ; une image sans prédécesseur
 # valide n'est jamais comptée. Un RESET peut masquer un état caché.
 start=0
 for i,e in enumerate(histoire):
  meta=e.result or {}
  if e.frame is None or e.frame.level!=courant.level or meta.get('game_over') or meta.get('level_completed') or meta.get('automatic') or meta.get('action_name')=='RESET' or str(getattr(e,'action','')).upper()=='RESET':
   start=i+1
 counts=defaultdict(lambda:[0,0]);
 for i in range(max(1,start+1),len(histoire)):
  prev,e=histoire[i-1],histoire[i];meta=e.result or {}
  if prev.frame is None or e.frame is None or prev.frame.level!=courant.level or e.frame.level!=courant.level:continue
  nom=meta.get('action_name','')
  # ACTION6 contient des coordonnées variables : ne pas les agréger.
  if not isinstance(nom,str) or not re.fullmatch(r'ACTION[1-57]',nom):continue
  if meta.get('automatic') or meta.get('game_over') or meta.get('level_completed'):continue
  n,unchanged=counts[nom];counts[nom]=[n+1,unchanged+int(prev.frame.grid==e.frame.grid)]
 lines=[f'{nom}: final image unchanged on {unchanged}/{n} recorded actions.' for nom,(n,unchanged) in sorted(counts.items()) if n>=minimum]
 if not lines:return ''
 result=HEADER
 for line in lines:
  if len((result+line+'\n').encode())>max_bytes:break
  result+=line+'\n'
 return '' if result==HEADER else result
