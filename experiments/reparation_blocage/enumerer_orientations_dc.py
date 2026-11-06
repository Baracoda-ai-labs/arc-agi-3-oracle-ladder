"""Énumération officielle de petites fonctions ; aucune transition de jeu en entrée."""
import json,signal
signal.alarm(20)
from dreamcoder.type import baseType,arrow,Context
from dreamcoder.program import Primitive
from dreamcoder.grammar import Grammar
phase=baseType('orientation_mod_pi')
ps=[Primitive('suivant',arrow(phase,phase),lambda x:(x+1)%4),Primitive('precedent',arrow(phase,phase),lambda x:(x-1)%4)]
ps += [Primitive('orientation_'+str(i),phase,i) for i in range(4)]
g=Grammar.uniform(ps);seen={};count=0
for lp,_,p in g.enumeration(Context.EMPTY,[],arrow(phase,phase),upperBound=9,maximumDepth=5):
 f=p.evaluate([]);v=tuple(f(x) for x in range(4));count+=1
 if v not in seen:seen[v]={'programme':str(p),'valeurs':v,'log_prior':lp}
 if count>=500:break
print(json.dumps({'backend':'DreamCoder officiel Grammar.enumeration','enumeres':count,'fonctions':list(seen.values())},indent=2))
