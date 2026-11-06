"""Worker officiel séparé : corpus JSON -> macros premier ordre apprises."""
import json,sys,hashlib,signal,time
signal.alarm(120)
from dreamcoder.type import baseType,arrow
from dreamcoder.program import Primitive,Program,Invented,Abstraction,Index,Application
from dreamcoder.grammar import Grammar
from dreamcoder.fragmentGrammar import FragmentGrammar
from dreamcoder.frontier import Frontier,FrontierEntry
from dreamcoder.task import Task
ast=baseType('ontology_ast');prims={}
def curry(f,n,args=()):return f(*args) if n==0 else lambda v:curry(f,n-1,args+(v,))
def primitive(key,arity,value):
 name='p'+hashlib.sha256(key.encode()).hexdigest()[:16]
 if name not in prims:prims[name]=Primitive(name,arrow(*([ast]*(arity+1))) if arity else ast,value)
 return prims[name]
def encoder(x,variables):
 if isinstance(x,str) and x.startswith('$'):return Index(len(variables)-1-variables.index(x))
 if isinstance(x,list):
  p=primitive('op:'+str(x[0])+':'+str(len(x)-1),len(x)-1,curry(lambda *args:[x[0],*args],len(x)-1))
  for v in x[1:]:p=Application(p,encoder(v,variables))
  return p
 return primitive('atom:'+json.dumps(x,sort_keys=True),0,x)
def vars(x):
 if isinstance(x,str) and x.startswith('$'):return {x}
 if isinstance(x,list):return set().union(*(vars(v) for v in x))
 return set()
corpus=json.load(open(sys.argv[1]));programmes=[]
for expr in corpus['conditions']:
 variables=sorted(vars(expr));p=encoder(expr,variables)
 for _ in variables:p=Abstraction(p)
 programmes.append((p,variables))
g=Grammar.uniform(list(prims.values()));fronts=[]
for i,(p,vs) in enumerate(programmes):
 tp=p.infer();fronts.append(Frontier([FrontierEntry(program=p,logPrior=g.logLikelihood(tp,p),logLikelihood=0.)],Task(str(i),tp,[])))
t=time.monotonic();g2,fs=FragmentGrammar.induceFromFrontiers(g,fronts,topK=1,aic=1.,structurePenalty=.001,a=1,CPUs=1)
mots={};refus=[]
for p in g2.primitives:
 if not isinstance(p,Invented):continue
 args=p.tp.functionArguments()
 if any(a!=ast for a in args) or p.tp.returns()!=ast or len(args)>6:refus.append(str(p));continue
 params=['$dc'+str(i) for i in range(len(args))];body=p.evaluate([])
 for param in params:body=body(param)
 name='dc_'+hashlib.sha256(str(p).encode()).hexdigest()[:12]
 mots[name]={'params':params,'corps':body,'sorte':'terme'}
for (p,vs),f,expr in zip(programmes,fs,corpus['conditions']):
 value=f.bestPosterior.program.evaluate([])
 for v in vs:value=value(v)
 assert value==expr
out={'mots':mots,'inventions_originales':[str(p) for p in g2.primitives if isinstance(p,Invented)],'refus_higher_order':refus,'donneurs':corpus['donneurs'],'conditions':len(fronts),'secondes':time.monotonic()-t,'commit_dreamcoder':'cb0e63f5c33cd2de360b791038b0f5272750270e','corpus_sha256':hashlib.sha256(json.dumps(corpus,sort_keys=True).encode()).hexdigest()}
json.dump(out,open(sys.argv[2],'w'),indent=2)
