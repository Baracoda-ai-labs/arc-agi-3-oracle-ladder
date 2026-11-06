"""Propriétaire SDK persistant : commandes bornées, jamais d'action pendant attente."""
import argparse,json,os,sys,time,signal,resource,subprocess
from pathlib import Path
import numpy as np
from boucle_objets_variables import LaboP1
from boucle_agent_integree import AUTORISES
from loi_orientation import prefixe,Orientation
from orientation_dirigee import Direction
from retour_perception import reviser
from revision_orientation import Revision
from retour_perception import charger

def main(args):
 assert args.jeu in AUTORISES
 r=Path(__file__).parent;out=args.sortie;out.mkdir(parents=True,exist_ok=False)
 debut=time.monotonic();cpu=time.process_time();kids=resource.getrusage(resource.RUSAGE_CHILDREN);actif=0.;attempts=0;acces=0;journal=[];repairs=0;confirmation=0;commandes=0
 base=args.source
 fs=json.loads((r/'orientations_dc.json').read_text())['fonctions'];_,_,pistes,_,_,_=prefixe(base,fs)
 anciens=charger(base,4);ref=charger(args.reprise/'N1/partie',len(json.loads((args.reprise/'N1/partie.json').read_text())['rows']))
 pool=json.loads((r/'directions_dc_structurees.json').read_text())['fonctions']
 mem=json.loads((args.reprise/'memoire_revisee_non_testee.json').read_text())
 for rules in mem['regles'].values():pool.extend(rules)
 l=None;description=None;o=None;state=None;statut='initialisation';lab=None
 signal.signal(signal.SIGALRM,lambda *a: (_ for _ in ()).throw(TimeoutError('budget actif')))
 def snapshot():
  children=resource.getrusage(resource.RUSAGE_CHILDREN)
  b={'pid':os.getpid(),'statut':statut,'session_ouverte':statut!='fermee','coups_reels':len(lab.rows) if lab else 0,'appels_tentes':attempts,'acces':acces,'initialisations':int(lab is not None),'commandes_progression':commandes,'representation':description,'secondes_actives':actif,'cpu_parent':time.process_time()-cpu,'cpu_enfants':children.ru_utime+children.ru_stime-kids.ru_utime-kids.ru_stime,'reparations':repairs,'confirmations_uniques_inedites':confirmation,'niveaux_gagnes':int(lab.won) if lab else 0,'promotion_durable':False}
  (out/'etat_session.json').write_text(json.dumps(b,indent=2)+'\n');(out/'journal.json').write_text(json.dumps(journal,indent=2)+'\n')
  if l:
   m=l.memoire();m['portee']=description;m['session_pid']=os.getpid();(out/'memoire_provisoire.json').write_text(json.dumps(m,indent=2)+'\n')
  return b
 def reconstruire(episodes):
  nonlocal l,description,o,state
  result=reviser(episodes,pistes)
  if result['statut']!='description_compatible':
   journal.append({'type':'retour_perception_non_resolu',**result});return False
  if description!=result['representation']:
   journal.append({'type':'retour_perception','depuis':description or 'axe_mod_pi','vers':result['representation'],'preuves':result['journal'],'regles_anciennes_revoquees':True})
  description=result['representation'];l=Revision([pool]);l.exemples=result['exemples']
  o=Direction(pistes) if description=='relation_dirigee' else Orientation()
  images,actions,films=episodes[-1];state=o.voir(images[0])
  for film in films:
   for frame in film:state=o.voir(frame)
  return True
 def ajuster(a):
  nonlocal repairs,pool
  if l.ajuster(a):return True
  if l.revisions and l.revisions[-1]['statut']=='representation_insuffisante':return False
  if repairs>=3:return False
  src=out/f'reparation_{repairs}_entree.json';dst=out/f'reparation_{repairs}_sortie.json';src.write_text(json.dumps({'exemples':l.exemples[str(a)],'fonctions':pool}));repairs+=1
  env={**os.environ,'DREAMCODER_CORE_ONLY':'1','PYTHONPATH':str(r/'vendor/dreamcoder')}
  subprocess.run([str(r/'vendor/dreamcoder/.venv/bin/python'),str(r/'reparer_direction_dc.py'),str(src),str(dst)],env=env,check=True,timeout=22)
  d=json.loads(dst.read_text());pool=pool+d['fonctions'];l.etages=[pool];journal.append({'type':'reparation_regle','action':a,'candidats':len(d['fonctions'])});return bool(l.candidats(a))
 def play(a,purpose):
  nonlocal attempts,state
  attempts+=1;snapshot();im,film=lab.play(a,purpose=purpose)
  for frame in film:state=o.voir(frame)
  return im,film
 signal.alarm(120)
 lab=LaboP1(args.jeu,1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',out/'N1/partie')
 assert reconstruire([anciens,ref])
 live=np.load(out/'N1/partie.npz')['images'][0];assert np.array_equal(live,ref[0][0])
 o=Direction(pistes) if description=='relation_dirigee' else Orientation();state=o.voir(live)
 for i,a in enumerate(ref[1]):
  im,film=play(a,'acces_compte_session_persistante');acces+=1
  assert np.array_equal(im,ref[0][i+1]) and np.array_equal(film,ref[2][i])
 actif+=time.monotonic()-debut;signal.alarm(0);statut='en_attente';print(json.dumps(snapshot()),flush=True)
 for line in sys.stdin:
  try:
   cmd=json.loads(line)
   if cmd['op']=='close':statut='fermee';print(json.dumps(snapshot()),flush=True);return
   if cmd['op']=='status':print(json.dumps(snapshot()),flush=True);continue
   if cmd['op']!='advance':raise ValueError('Commande inconnue')
   n=cmd.get('coups',1)
   if not isinstance(n,int) or not 1<=n<=4:raise ValueError('Commande hors budget')
   commandes+=1;t=time.monotonic();signal.alarm(max(1,int(120-actif)))
   try:
    for _ in range(n):
     if len(lab.rows)>=32 or lab.finished or actif+time.monotonic()-t>=120:statut='budget_ou_fin';break
     if not all(ajuster(a) for a in (1,2,3,4)):statut='revision_requise';break
     ids=[0] if description=='relation_dirigee' else sorted(pistes)
     if any(k not in state for k in ids):statut='perception_incomplete';break
     choix=l.choix([state[k] for k in ids],lab.actions_disponibles)
     if choix is None:statut='couverture_locale_epuisee';break
     a=choix['action'];before=state.copy();ps={k:l.predire(a,before[k]) for k in ids};novel={k:l.nouveau(a,[before[k]]) for k in ids}
     row={'type':'experience','choix':choix,'avant':before,'predictions':ps,'nouveau':novel};journal.append(row)
     play(a,'navigation_experience' if choix['acces'] else 'experience_prospective')
     row['apres']=state.copy();row['refute']=any(k not in state or state[k] not in ps[k] for k in ids)
     confirmation+=sum(novel[k] and len(ps[k])==1 and state.get(k)==ps[k][0] for k in ids)
     # Retour au signal brut avant toute réparation grammaticale.
     current=charger(out/'N1/partie',len(lab.rows))
     if not reconstruire([anciens,current]):statut='perception_non_resolue';break
     if not ajuster(a):statut='revision_requise';break
     statut='en_attente'
   finally:actif+=time.monotonic()-t;signal.alarm(0)
   print(json.dumps(snapshot()),flush=True)
  except Exception as e:
   statut='erreur_commande';journal.append({'type':'erreur','message':repr(e)});print(json.dumps(snapshot()),flush=True)
 # EOF : fermeture explicite signalée, jamais prétendre session vivante.
 statut='fermee';snapshot()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--jeu',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--reprise',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);main(p.parse_args())
