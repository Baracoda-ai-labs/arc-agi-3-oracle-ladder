from .poussee_generale import PousseeGenerale
from .laboratoire import Laboratoire
from pathlib import Path
from collections import Counter
import json,time

def run(level,jeux,output,budget=150,seconds=90,lab=None):
 out=Path(output);out.mkdir(parents=True,exist_ok=True);lab=lab or Laboratoire('ka59',level,jeux,out/'partie');t0=time.monotonic();events=[];plan=[];reason='budget';m=None
 try:
  m=PousseeGenerale(lab.image);state=m.start;visits=Counter();events.append(dict(type='image_geometry',model=m.describe()))
  while not lab.finished and len(lab.rows)<budget-2 and time.monotonic()-t0<seconds:
   if not plan:
    r=m.solve(state,seconds=min(1,max(.01,seconds-(time.monotonic()-t0))));
    if not r.get('actions') and m.h(state)>0:r=m.subgoal(state,seconds=min(3,max(.01,seconds-(time.monotonic()-t0))))
    plan=r.get('actions',[]);events.append(dict(step=len(lab.rows),type='search',status=r['status'],nodes=r['nodes']))
   purpose='plan_provisoire'
   if not plan:
    candidates=[]
    for a in list(range(4))+[4+i for i in m.selectable]:
     ns=m.step(state,a)
     if visits[(state,a)]==0:candidates.append((ns==state,lab.economy.cost_upper([m.concrete(state,a)]),m.h(ns),a))
    if not candidates:reason='etat_sature';break
    plan=[min(candidates)[-1]];purpose='experience_nouvelle'
   real_plan=[];preview=state
   for aa in plan:
    real_plan.append(m.concrete(preview,aa));preview=m.step(preview,aa)
   if not lab.economy.admissible(real_plan):
    prefix=[]
    for real in real_plan:
     if not lab.economy.admissible(prefix+[real]):break
     prefix.append(real)
    events.append(dict(step=len(lab.rows),type='plan_borne_par_jauge',original=len(plan),authorized=len(prefix)))
    if not prefix:reason='jauge_insuffisante';break
    plan=plan[:len(prefix)]
   a=plan.pop(0);pred=m.step(state,a)
   if visits[(state,a)]>=1:plan=[];m.blocked.add((state,a));continue
   visits[(state,a)]+=1;real=m.concrete(state,a);image,_=lab.play(real,purpose)
   if lab.finished:break
   actual=m.observe(image,pred)
   if actual is None:reason='perception_perdue';break
   if actual!=pred:
    events.append(dict(step=len(lab.rows),type='counterexample',predicted=pred,observed=actual,action=real));plan=[]
    if actual==state:m.blocked.add((state,a))
   state=actual
  if time.monotonic()-t0>=seconds:reason='temps'
 except __import__('boucle_v4.economie',fromlist=['BudgetInconnu']).BudgetInconnu as e:
  reason='abstention_economie';events.append(dict(type='economy_stop',message=str(e)))
 except Exception as e:
  import traceback
  reason='exception_contenue';events.append(dict(type='exception',name=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
 result=dict(game='ka59',level=level,victory=lab.won,actions=len(lab.rows),seconds=time.monotonic()-t0,reason='victoire_reelle' if lab.won else ('defaite_reelle' if lab.finished else reason),events=events,model=m.describe() if m else None)
 result['economy']=lab.economy.report()
 (out/'diagnostic.json').write_text(json.dumps(result,indent=2));return result
