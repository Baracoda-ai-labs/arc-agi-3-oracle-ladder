"""Un propriétaire SDK : accès archivé, mémoire commune, transfert observé à chaque coup."""
import argparse,json,time,hashlib,signal
from pathlib import Path
import numpy as np
from boucle_agent_integree import AUTORISES,empreintes,sauver
from boucle_objets_variables import LaboP1
from chaine_agent_integree import AgentIntegre
from preparer_modele_transfert import depuis_trace
from issues_observees import issue_sdk

def main(args):
 if args.jeu not in AUTORISES:raise ValueError('Jeu non autorisé')
 out=args.sortie;out.mkdir(parents=True,exist_ok=False)
 start=time.monotonic();cpu=time.process_time();m,access,images,histoire=depuis_trace(args.source,[1,2,3,4,5])
 sauver(out/'modele_source.json',{'provenance':m.provenance,'famille':m.famille,'promotion_durable':False})
 sauver(out/'reconstruction_traces.json',histoire)
 hashes=empreintes();sauver(out/'sources.json',hashes)
 lab=None;previous=None;agent=None;status='acces';attempts=0;records=[]
 def bilan():
  total=(len(previous.rows) if previous else 0)+(len(lab.rows) if lab else 0)
  b=dict(jeu=args.jeu,statut=status,coups_reels=total,coups_acces=len(previous.rows) if previous else total,coups_transfert=len(lab.rows) if previous else 0,appels_tentes=attempts,initialisations=int(lab is not None),niveaux_gagnes=(1 if previous else 0)+int(lab.won) if lab else 0,jeu_gagne=bool(lab and lab.partie_gagnee),secondes=time.monotonic()-start,cpu_s=time.process_time()-cpu,sources_inchangees=hashes==empreintes(hashes))
  sauver(out/'bilan.json',b);sauver(out/'decisions.json',records)
  if agent:sauver(out/'journal.json',agent.journal)
  return b
 def expired(*_):raise TimeoutError('Temps global atteint')
 signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,args.secondes)
 try:
  lab=LaboP1(args.jeu,1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',out/'N1/partie')
  if not np.array_equal(lab.image,images[0]):raise ValueError('Etat initial différent de accès archivé')
  for i,a in enumerate(access):
   if lab.finished:break
   attempts+=1;lab.play(a,purpose='acces_N2_archive_compte');bilan()
   if not np.array_equal(lab.image,images[i+1]):raise ValueError('Accès divergent, ne pas continuer aveuglément')
  if not lab.won:raise ValueError('Accès niveau suivant non gagné')
  previous=lab;lab=lab.next_level(out/'N2/partie');assert lab.env is previous.env
  agent=AgentIntegre([lab.image],[],[],[],limite=args.coups-len(previous.rows),decouverte_courte=True,routage_classes=True)
  agent.installer_modele_jeu(m);status='transfert'
  while not lab.finished and len(previous.rows)+len(lab.rows)<args.coups:
   if hashes!=empreintes(hashes):raise ValueError('Code modifié pendant mesure')
   d=agent.decider(lab.actions_disponibles,secondes=min(4,args.secondes-(time.monotonic()-start)))
   rec={'avant_coup_total':attempts+1,'decision':d};records.append(rec);bilan()
   if not d.get('actions'):status=d['statut'];break
   a=d['actions'][0]
   if (6 if isinstance(a,list) else a) not in lab.actions_disponibles:raise ValueError('Action absente')
   attempts+=1;im,film=lab.play(a,purpose='transfert_chaine_commune')
   rec['observation']=agent.observer(a,im,film,issue_sdk(lab.rows[-1]['state'],lab.rows[-1]['levels_completed'],lab.completed_baseline));bilan()
  if lab.finished:status='victoire_reelle' if lab.won else 'defaite_reelle'
 except Exception as e:
  status='interruption';sauver(out/'erreur.json',{'erreur':repr(e)})
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);print(json.dumps(bilan()),flush=True)
 if args.attendre:
  print('SESSION_CONSERVEE',flush=True)
  for line in __import__('sys').stdin:
   if line.strip()=='status':print(json.dumps(bilan()),flush=True)
   elif line.strip()=='close':break

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--jeu',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);p.add_argument('--coups',type=int,default=80);p.add_argument('--secondes',type=float,default=120);p.add_argument('--attendre',action='store_true');main(p.parse_args())
