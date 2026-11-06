"""Expérience bornée guidée par désaccord, un propriétaire SDK et films intégraux."""
import json,time,resource,signal,argparse,hashlib
from pathlib import Path
import numpy as np
from loi_orientation import prefixe,Orientation
from boucle_objets_variables import LaboP1
from boucle_agent_integree import AUTORISES
ap=argparse.ArgumentParser();ap.add_argument('--jeu',required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--sortie',type=Path,required=True);args=ap.parse_args()
assert args.jeu in AUTORISES
args.sortie.mkdir(parents=True,exist_ok=False)
r=Path(__file__).parent;fs=json.loads((r/'orientations_dc.json').read_text())['fonctions']
_,lois,ids,states,z,_=prefixe(args.source,fs);assert ids
initial=z['images'][0].copy();o=Orientation();logs=[];t=time.monotonic();cpu=time.process_time();lab=None;attempts=0
signal.signal(signal.SIGALRM,lambda *a: (_ for _ in ()).throw(TimeoutError('60s')));signal.alarm(60)
try:
 lab=LaboP1(args.jeu,1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',args.sortie/'N1/partie')
 live=np.load(args.sortie/'N1/partie.npz')['images'][0];assert np.array_equal(live,initial),'Archive initiale différente : ne pas transférer les identités'
 state=o.voir(live)
 for step in range(12):
  if lab.finished:break
  a=lois.choisir(state,ids,lab.actions_disponibles)
  if a is None:break
  ps={k:lois.predire(a,state[k]) for k in ids if k in state}
  avant={k:len(lois.candidats(a)) for k in ps}
  novel={k:not any(b==state[k] for b,c in lois.exemples.get(str(a),[])) for k in ps}
  record={'action':a,'avant':{k:state[k] for k in ps},'predictions':ps,'nouveau':novel,'hypotheses_avant':avant};logs.append(record)
  (args.sortie/'journal.json').write_text(json.dumps(logs,indent=2))
  attempts+=1;im,film=lab.play(a,purpose='discrimination_loi_orientation_DreamCoder')
  for frame in film:after=o.voir(frame)
  record['apres']={k:after.get(k) for k in ps};record['refutations']=[]
  for k in ps:
   if k not in after:record['refutations'].append(k);continue
   if after[k] not in ps[k]:record['refutations'].append(k)
   lois.ajouter(a,state[k],after[k])
  record['hypotheses_apres']=len(lois.candidats(a));state=after
  if record['refutations']:break
finally:
 signal.alarm(0)
 (args.sortie/'journal.json').write_text(json.dumps(logs,indent=2))
 bilan={'coups':len(lab.rows) if lab else 0,'appels_tentes':attempts,'init':int(lab is not None),'secondes':time.monotonic()-t,'cpu_s':time.process_time()-cpu,'niveaux_gagnes':int(lab.won) if lab else 0,'jeu_gagne':lab.partie_gagnee if lab else False,'regles':{str(a):lois.candidats(a) for a in (1,2,3,4)},'portee':'orientation modulo pi uniquement ; ni contact, ni but, ni simulateur complet','prefixe_ancien_apprentissage':4}
 (args.sortie/'bilan.json').write_text(json.dumps(bilan,indent=2));print(json.dumps(bilan))
