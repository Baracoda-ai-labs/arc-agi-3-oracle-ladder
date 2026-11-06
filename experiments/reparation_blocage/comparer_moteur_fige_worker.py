"""Processus lecture seule : ne reçoit qu'un historique de préfixe."""
import json,sys,time
from pathlib import Path
from chrysalide.arc3.moteur import MoteurC
h=json.loads(Path(sys.argv[1]).read_text());m=MoteurC(budget=12);t=time.monotonic()
result=m.proposer(h)
out={'secondes':time.monotonic()-t,'infos':m.infos,'plan':result[0] if result else None,'programme':result[1] if result and len(result)>1 else None,'module':sys.modules[MoteurC.__module__].__file__,'victoire_verifiee':False}
Path(sys.argv[2]).write_text(json.dumps(out,default=repr,indent=2))
