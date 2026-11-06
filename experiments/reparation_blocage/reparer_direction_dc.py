"""Réparation conditionnelle DreamCoder des meilleurs programmes partiels."""
import json,sys,signal,hashlib,time
signal.alarm(20)
from dreamcoder.type import baseType,arrow,Context
from dreamcoder.program import Primitive
from dreamcoder.grammar import Grammar
source=json.load(open(sys.argv[1]));es=source['exemples'];pool=source['fonctions']
rank=sorted(pool,key=lambda f:(-sum(f['valeurs'][x]==y for x,y in es),len(f['programme']),f['programme']))[:8]
regle=baseType('transformation_orientation8');phase=baseType('orientation8');ps=[];parents={}
for f in rank:
 name='hyp_'+hashlib.sha256(json.dumps(f['valeurs']).encode()).hexdigest()[:12];vals=f['valeurs'];parents[name]=f
 if not any(p.name==name for p in ps):ps.append(Primitive(name,regle,lambda x,vs=vals:vs[x]))
ps += [Primitive('identite',regle,lambda x:x),Primitive('suivant',regle,lambda x:(x+1)%8),Primitive('precedent',regle,lambda x:(x-1)%8)]
ps += [Primitive('phase_'+str(i),phase,i) for i in range(8)]
ps += [Primitive('si_egal',arrow(phase,regle,regle,regle),lambda k:lambda a:lambda b:lambda x:a(x) if x==k else b(x)),Primitive('si_inferieur',arrow(phase,regle,regle,regle),lambda k:lambda a:lambda b:lambda x:a(x) if x<k else b(x))]
g=Grammar.uniform(ps);out={};count=0;t=time.monotonic()
for lp,_,p in g.enumeration(Context.EMPTY,[],regle,upperBound=15,maximumDepth=4):
 f=p.evaluate([]);v=tuple(f(x) for x in range(8));count+=1
 if all(v[x]==y for x,y in es) and v not in out:out[v]={'programme':str(p),'valeurs':v,'log_prior':lp}
 if count>=100000:break
json.dump({'backend':'DreamCoder officiel','parents':parents,'enumeres':count,'secondes':time.monotonic()-t,'fonctions':list(out.values())},open(sys.argv[2],'w'),indent=2)
