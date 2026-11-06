"""Smoke CPU du compresseur original : abstraction découverte, pas préécrite."""
import json,signal,time
signal.alarm(60)
from dreamcoder.type import tint,arrow,Context
from dreamcoder.program import Primitive,Program,Invented
from dreamcoder.grammar import Grammar
from dreamcoder.frontier import Frontier,FrontierEntry
from dreamcoder.task import Task
from dreamcoder.fragmentGrammar import FragmentGrammar
primitives=[Primitive('inc',arrow(tint,tint),lambda x:x+1)]+[Primitive(f'n{i}',tint,i) for i in range(8)]
g=Grammar.uniform(primitives)
fs=[]
for i in range(8):
 p=Program.parse(f'(inc (inc (inc n{i})))')
 t=Task(f'example_{i}',tint,[((),i+3)])
 fs.append(Frontier([FrontierEntry(program=p,logPrior=g.logLikelihood(tint,p),logLikelihood=0.)],task=t))
t0=time.monotonic()
g2,fs2=FragmentGrammar.induceFromFrontiers(g,fs,topK=1,aic=1.,structurePenalty=.001,a=1,CPUs=1)
learned=[str(p) for p in g2.primitives if isinstance(p,Invented)]
assert learned,'Aucune abstraction apprise'
for f in fs2:
 assert f.bestPosterior.program.evaluate([])==f.task.examples[0][1]
items=[]
for logp,ctx,p in g2.enumeration(Context.EMPTY,[],tint,upperBound=15,maximumDepth=8):
 items.append(str(p))
 if len(items)>=12:break
assert items
print(json.dumps({'commit':'cb0e63f5c33cd2de360b791038b0f5272750270e','backend':'original FragmentGrammar CPython','cpu_workers':1,'elapsed_s':time.monotonic()-t0,'learned':learned,'rewritten':[str(f.bestPosterior.program) for f in fs2],'semantics_checked':len(fs2),'enumerated':items},indent=2))
