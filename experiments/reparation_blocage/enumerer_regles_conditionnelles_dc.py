"""Grammaire typée de transformations et conditions, sans données ARC."""
import json,time,signal
signal.alarm(20)
from dreamcoder.type import baseType,arrow,Context
from dreamcoder.program import Primitive
from dreamcoder.grammar import Grammar
phase=baseType('orientation8');regle=baseType('transformation_orientation8')
ps=[Primitive('identite',regle,lambda x:x),Primitive('suivant',regle,lambda x:(x+1)%8),Primitive('precedent',regle,lambda x:(x-1)%8)]
ps+=[Primitive('phase_'+str(i),phase,i) for i in range(8)]
ps += [Primitive('constante',arrow(phase,regle),lambda k:lambda x:k),Primitive('si_egal',arrow(phase,regle,regle,regle),lambda k:lambda a:lambda b:lambda x:a(x) if x==k else b(x)),Primitive('si_inferieur',arrow(phase,regle,regle,regle),lambda k:lambda a:lambda b:lambda x:a(x) if x<k else b(x)),Primitive('composer',arrow(regle,regle,regle),lambda a:lambda b:lambda x:a(b(x)))]
g=Grammar.uniform(ps);seen={};count=0;t=time.monotonic()
for lp,_,p in g.enumeration(Context.EMPTY,[],regle,upperBound=14,maximumDepth=5):
 f=p.evaluate([]);v=tuple(f(x) for x in range(8));count+=1
 if v not in seen or len(str(p))<len(seen[v]['programme']):seen[v]={'programme':str(p),'valeurs':v,'log_prior':lp}
 if count>=100000:break
print(json.dumps({'backend':'DreamCoder officiel Grammar.enumeration','enumeres':count,'secondes':time.monotonic()-t,'fonctions':list(seen.values())},indent=2))
