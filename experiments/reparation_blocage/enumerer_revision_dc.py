"""Élargissement générique, sans exemples de jeu ni formule cible."""
import json,signal,sys,time
signal.alarm(20)
from dreamcoder.type import baseType,arrow,Context
from dreamcoder.program import Primitive
from dreamcoder.grammar import Grammar
phase=baseType('orientation_mod_pi');stage=int(sys.argv[1]);t=time.monotonic()
ps=[Primitive('suivant',arrow(phase,phase),lambda x:(x+1)%4),Primitive('precedent',arrow(phase,phase),lambda x:(x-1)%4)]
ps += [Primitive('orientation_'+str(i),phase,i) for i in range(4)]
ps += [Primitive('plus',arrow(phase,phase,phase),lambda x:lambda y:(x+y)%4),Primitive('moins',arrow(phase,phase,phase),lambda x:lambda y:(x-y)%4),Primitive('fois',arrow(phase,phase,phase),lambda x:lambda y:x*y%4)]
if stage==2:ps.append(Primitive('si_egal',arrow(phase,phase,phase,phase,phase),lambda x:lambda y:lambda a:lambda b:a if x==y else b))
g=Grammar.uniform(ps);seen={};count=0
for lp,_,p in g.enumeration(Context.EMPTY,[],arrow(phase,phase),upperBound=11,maximumDepth=5):
 f=p.evaluate([]);v=tuple(f(x) for x in range(4));count+=1
 if v not in seen or len(str(p))<len(seen[v]['programme']):seen[v]={'programme':str(p),'valeurs':v,'log_prior':lp}
 if count>=10000:break
print(json.dumps({'backend':'DreamCoder officiel','etage':stage,'enumeres':count,'secondes':time.monotonic()-t,'fonctions':list(seen.values())},indent=2))
