"""Rejouer causalement une observation acquise avec les réparateurs communs."""
from pathlib import Path
import argparse, hashlib, json
from avancer_agent_relais import charger_agent, sauver_agent

def main():
    p=argparse.ArgumentParser();p.add_argument('--avant',required=True);p.add_argument('--observe',required=True);p.add_argument('--sortie',required=True);args=p.parse_args()
    a=charger_agent(Path(args.avant));b=charger_agent(Path(args.observe));n=len(a.actions)
    assert len(b.actions)==n+1
    decision={'statut':'rejeu_observation_acquise','actions':[b.actions[n]]}
    a._suivre_experience(decision);a.attente=decision
    r=a.observer(b.actions[n],b.images[n+1],b.films[n],b.issues[n],source='trace')
    assert a.chaines
    out=Path(args.sortie);out.mkdir(exist_ok=False)
    sauver_agent(a,out/'agent.pkl')
    rapport={'sdk':0,'coup':n+1,'sources':{x:hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in (args.avant,args.observe)},'modeles':list(a.chaines),'reparations':[e for e in a.journal if e.get('type')=='revision_sol_revele'],'causal':True,'buts_non_confirmes':True}
    (out/'rapport.json').write_text(json.dumps(rapport,indent=2));print(json.dumps({'sortie':str(out),'modeles':len(a.chaines),'sdk':0}))
if __name__=='__main__':main()
