"""Garde optionnelle pour un message Franzen. La valeur par défaut est muette."""
import os
from .faits_franzen import faits_finaux

def contexte(histoire,courant):
 if os.environ.get('CHRYS_FAITS','0')!='1' or courant is None or not histoire:return ''
 try:
  seuil=max(0,int(os.environ.get('CHRYS_FAITS_APRES','40')))
  n=0
  for entree in reversed(histoire):
   if entree.frame is None or entree.frame.level!=courant.level:break
   meta=entree.result or {}
   if meta.get('game_over') or meta.get('level_completed') or meta.get('automatic') or meta.get('action_name')=='RESET' or str(getattr(entree,'action','')).upper()=='RESET':break
   if meta.get('action_name') in ('ACTION1','ACTION2','ACTION3','ACTION4','ACTION5','ACTION6','ACTION7'): n+=1
  if n<seuil:return ''
  out=faits_finaux(histoire,courant)
  return '\n\n'+out if out else ''
 except (AttributeError,TypeError,ValueError):
  return ''
