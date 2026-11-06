import time,json,numpy as np
from pathlib import Path
from collections import Counter
from .fantome_general import FantomeGeneral
from .laboratoire import Laboratoire

def run(level,jeux,output,budget=150,seconds=90,lab=None):
 out=Path(output);out.mkdir(parents=True,exist_ok=True)
 lab=lab or Laboratoire('g50t',level,jeux,out/'partie');t0=time.monotonic();events=[];predictions=[];plan=[];visits=Counter();reason='budget';model=None
 try:
  for a in range(1,5):
   if len(lab.rows)>=budget or lab.finished:break
   b=lab.image.copy();im,_=lab.play(a,'identifier_translation')
   try:model=FantomeGeneral(b,im,a);break
   except (ValueError,IndexError) as e:events.append(dict(step=len(lab.rows),type='identification',message=str(e)))
  if model is None:reason='perception_non_identifiee'
  else:
   state=model.step_state(model.initial,a);events.append(dict(step=len(lab.rows),type='geometry',description=model.describe()))
   # Motion identification already crossed a trigger: synchronize observed bits.
   def sync(s,image):
    p,routes,idx,record,bits=s;occ=model.occupants(p,routes,idx)
    for g,group in enumerate(model.groups):
     if group['kind']!='toggle':continue
     for dp in group['doors']:
      if dp in occ:continue
      closed=sum(image[dp[1]+v,dp[0]+u]==group['color'] for u,v in model.shape)>=len(model.shape)*.5
      bits=bits&~(1<<g) if closed else bits|(1<<g)
    return p,routes,idx,record,bits
   state=sync(state,lab.image);blocked=set();model.blocked=blocked
   from .memoire_induite import MemoireInduite
   memory=MemoireInduite(model,model.capacity_hint)
   memory.update(a,state[0],lab.image)
   history=[]
   while len(lab.rows)<budget-2 and not lab.finished and time.monotonic()-t0<seconds:
    key=state
    if not plan:
     r=model.solve(state,seconds=min(1.5,max(.01,seconds-(time.monotonic()-t0))))
     events.append(dict(step=len(lab.rows),type='search',status=r['status'],nodes=r['nodes']))
     plan=r.get('actions',[])
    purpose='plan_provisoire'
    if not plan:
     from .discrimination import choisir
     import copy
     variants=[]
     for h in memory.hypotheses:
      if h['errors']==0 and h['clock']=='effective' and (h['capacity'],h['policy']) not in {(q.capacity,q.overflow) for q in variants}:
       variant=copy.copy(model);variant.capacity=h['capacity'];variant.overflow=h['policy'];variants.append(variant)
     probe=choisir(variants,[state]*len(variants),lab.economy,maxdepth=3,forbidden=[a for a in range(1,6) if visits[(key,a)]])
     if probe:
      plan=probe['actions'];purpose='experience_discriminante';events.append(dict(step=len(lab.rows),type='discrimination',**probe))
    if not plan:
     # Reach a yet untested trigger / novel place via safe candidate navigation.
     choices=[]
     for target in model.nodes:
      nav=model.nav(state,target)
      if nav and nav[1] and lab.economy.admissible(nav[1]):
       score=(visits[('pose',target)],0 if target in model.triggers else 1,lab.economy.cost_upper(nav[1]),len(nav[1]),target)
       choices.append((score,nav[1]))
     if choices:plan=min(choices)[1];purpose='exploration_objet_ou_position'
     else:
      options=[a for a in range(1,6) if visits[(key,a)]==0 and model.step_state(state,a) is not None]
      if not options:reason='aucune_experience_nouvelle_sous_modele';break
      plan=[options[0]];purpose='experience_non_repetee'
    if not lab.economy.admissible(plan):
     prefix=[]
     for candidate in plan:
      if not lab.economy.admissible(prefix+[candidate]):break
      prefix.append(candidate)
     events.append(dict(step=len(lab.rows),type='plan_borne_par_jauge',original=len(plan),authorized=len(prefix)))
     if not prefix:reason='jauge_insuffisante';break
     plan=prefix
    a=plan.pop(0)
    if visits[(key,a)]>=1:
     plan=[];alternatives=[v for v in range(1,6) if not visits[(key,v)] and model.step_state(state,v) is not None]
     if not alternatives:reason='etat_sature';break
     a=alternatives[0];purpose='discrimination_anti_boucle'
    visits[(key,a)]+=1
    expected=model.step_state(state,a)
    if expected is None:plan=[];continue
    before=state;image,_=lab.play(a,purpose);history.append((a,image.copy()))
    if lab.finished:break
    actual=model.observe_player(image,expected[0])
    if actual is None:reason='controle_perdu';break
    if actual!=expected[0]:
     events.append(dict(step=len(lab.rows),type='counterexample_position',predicted=expected[0],observed=actual))
     if actual==before[0] and a in range(1,5):
      blocked.add((actual,a));expected=before
     else:expected=(actual,expected[1],expected[2],expected[3],expected[4])
     plan=[]
    observed=sync(expected,image)
    if observed[4]!=expected[4]:
     events.append(dict(step=len(lab.rows),type='counterexample_toggle',predicted=expected[4],observed=observed[4],action=a));plan=[]
     if a==5:model.reset_bits=not model.reset_bits
    mh=memory.update(a,actual,image)
    if mh is not None and (model.capacity!=mh['capacity'] or model.overflow!=mh['policy']):
     events.append(dict(step=len(lab.rows),type='memoire_selection_par_rejeu',capacity=mh['capacity'],policy=mh['policy'],clock=mh['clock']))
     model.capacity=mh['capacity'];model.overflow=mh['policy'];plan=[]
    if mh is not None:observed=(observed[0],mh['routes'],mh['idx'],mh['record'],observed[4])
    state=observed;visits[('pose',actual)]+=1
    predictions.append(dict(step=len(lab.rows),player=actual,expected_player=expected[0],bits=state[4]))
   if time.monotonic()-t0>=seconds:reason='temps'
 except __import__('boucle_v4.economie',fromlist=['BudgetInconnu']).BudgetInconnu as e:
  reason='abstention_economie';events.append(dict(type='economy_stop',message=str(e)))
 except Exception as e:
  import traceback
  reason='exception_contenue';events.append(dict(type='exception',name=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
 result=dict(game='g50t',level=level,victory=lab.won,actions=len(lab.rows),seconds=time.monotonic()-t0,reason='victoire_reelle' if lab.won else ('defaite_reelle' if lab.finished else reason),events=events,predictions=predictions,model=model.describe() if model else None)
 result['economy']=lab.economy.report()
 if 'memory' in locals():result['memory_hypotheses']=memory.report()
 (out/'diagnostic.json').write_text(json.dumps(result,indent=2));return result
