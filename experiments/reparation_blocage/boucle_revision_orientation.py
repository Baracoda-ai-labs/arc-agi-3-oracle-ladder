"""Révision prospective sur SDK, bibliothèques génériques figées avant actions."""
import argparse,json,time,signal,hashlib
from pathlib import Path
import numpy as np
from boucle_objets_variables import LaboP1
from boucle_agent_integree import AUTORISES
from loi_orientation import prefixe,Orientation
from revision_orientation import Revision

def main(args):
 assert args.jeu in AUTORISES
 r=Path(__file__).parent;out=args.sortie;out.mkdir(parents=True,exist_ok=False)
 etages=[json.loads((r/n).read_text())['fonctions'] for n in ('orientations_dc.json','orientations_dc_arithmetique.json','orientations_dc_conditions.json','orientations_dc_conditions_larges.json')]
 _,old,ids,_,z,_=prefixe(args.source,etages[0]);l=Revision(etages);l.exemples=old.exemples
 anciens=[]
 for dossier in [*args.preuves,args.reprise]:anciens.extend(json.loads((dossier/'journal.json').read_text()))
 ref=np.load(args.reprise/'N1/partie.npz')
 acces_rows=json.loads((args.reprise/'N1/partie.json').read_text())['rows']
 for row in anciens:
  for k,b in row.get('avant',{}).items():
   c=row.get('apres',{}).get(k)
   if c is not None:l.ajouter(row.get('action',row.get('choix',{}).get('action')),b,c)
 for a in (1,2,3,4):assert l.ajuster(a),'Représentation initiale insuffisante'
 ids=sorted(ids);o=Orientation();journal=[];t=time.monotonic();cpu=time.process_time();lab=None;attempts=0;status='budget';acces=0
 def save():
  (out/'journal.json').write_text(json.dumps(journal,indent=2)+'\n')
  (out/'memoire_provisoire.json').write_text(json.dumps(l.memoire(),indent=2)+'\n')
 def play(a,purpose):
  nonlocal attempts
  attempts+=1;save();im,film=lab.play(a,purpose=purpose)
  for frame in film:state=o.voir(frame)
  return im,film,state
 signal.signal(signal.SIGALRM,lambda *a: (_ for _ in ()).throw(TimeoutError('120s')));signal.alarm(120)
 try:
  lab=LaboP1(args.jeu,1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',out/'N1/partie')
  live=np.load(out/'N1/partie.npz')['images'][0];assert np.array_equal(live,z['images'][0]);state=o.voir(live)
  for i,row in enumerate(acces_rows):
   im,film,state=play(row['action'],'acces_compte_et_verifie');acces+=1
   assert np.array_equal(im,ref['images'][i+1]) and np.array_equal(film,ref[f'film_{i+1}'])
   journal.append({'type':'acces','action':row['action'],'film_identique':True})
  while len(lab.rows)<24 and not lab.finished:
   if not all(k in state for k in ids):status='perception_incomplete';break
   choix=l.choix([state[k] for k in ids],lab.actions_disponibles)
   if choix is None:status='espace_orientation_couvert';break
   a=choix['action'];ps={k:l.predire(a,state[k]) for k in ids}
   novel={k:l.nouveau(a,[state[k]]) for k in ids}
   entry={'type':'experience','choix':choix,'avant':{k:state[k] for k in ids},'predictions':ps,'nouveau':novel};journal.append(entry)
   im,film,after=play(a,'route_vers_experience' if choix['acces'] else 'hypothese_experience_revision')
   entry['apres']={k:after.get(k) for k in ids};entry['refute']=any(k not in after or after[k] not in ps[k] for k in ids)
   for k in ids:
    if k not in after:continue
    if novel[k] and len(ps[k])==1 and ps[k][0]==after[k]:l.confirmations.append({'coup':len(lab.rows),'action':a,'piste':k,'entree':state[k],'sortie':after[k],'statut':'prediction_nouvelle_confirmee'})
    l.ajouter(a,state[k],after[k])
   ok=l.ajuster(a);entry['etage_apres']=l.niveaux.get(str(a),0);entry['candidats_restants']=len(l.candidats(a));state=after;save()
   if not ok:status='representation_ou_grammaire_non_couverte';break
  if lab.won:status='victoire_reelle'
 finally:
  signal.alarm(0);save()
  b={'statut':status,'coups_reels':len(lab.rows) if lab else 0,'appels_tentes':attempts,'initialisations':int(lab is not None),'coups_acces':acces,'niveaux_gagnes':int(lab.won) if lab else 0,'jeu_gagne':lab.partie_gagnee if lab else False,'secondes':time.monotonic()-t,'cpu_s':time.process_time()-cpu,'confirmations':len(l.confirmations),'revisions':l.revisions,'promotion_durable':False}
  (out/'bilan.json').write_text(json.dumps(b,indent=2)+'\n');print(json.dumps(b))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--jeu',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--reprise',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);p.add_argument('--preuves',type=Path,action='append',default=[]);main(p.parse_args())
