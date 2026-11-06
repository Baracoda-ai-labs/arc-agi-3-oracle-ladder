"""Rejeu causal des observations conservées, puis décision ordinaire hors SDK."""
from pathlib import Path
import argparse,json,hashlib,time
from avancer_agent_relais import charger_agent,sauver_agent
from buts_roles_herites import admettre

def main():
 p=argparse.ArgumentParser();p.add_argument('--avant',required=True);p.add_argument('--observe',required=True);p.add_argument('--sortie',required=True);p.add_argument('--offre',type=int,nargs='+',required=True);p.add_argument('--secondes',type=float,default=30);args=p.parse_args()
 a=charger_agent(Path(args.avant));b=charger_agent(Path(args.observe));records=[]
 for i in range(len(a.actions),len(b.actions)):
  d={'statut':'rejeu_observation_acquise','actions':[b.actions[i]]};a._suivre_experience(d);a.attente=d
  r=a.observer(b.actions[i],b.images[i+1],b.films[i],b.issues[i],source='trace')
  records.append({'coup':i+1,'statuts':[x['statut'] for x in r['resultats']]})
 admettre(a,2)
 out=Path(args.sortie);out.mkdir(exist_ok=False);sauver_agent(a,out/'agent.pkl')
 depart=time.process_time();decision=a.decider(args.offre,args.secondes);cpu=time.process_time()-depart
 sauver_agent(a,out/'agent.pkl')
 # Les prédictions complètes sont conservées pour contrôler le futur lot réel.
 (out/'decision.json').write_text(json.dumps(decision))
 rapport={'sdk':0,'sources':{x:hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in (args.avant,args.observe)},'rejeu':records,'modeles':list(a.chaines),'statut':decision.get('statut'),'actions':decision.get('actions'),'cpu_parent_decision':cpu}
 (out/'rapport.json').write_text(json.dumps(rapport,indent=2));print(json.dumps(rapport))
if __name__=='__main__':main()
