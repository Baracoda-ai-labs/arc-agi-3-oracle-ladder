"""Rejeu causal d'observations acquises, sans recherche ni SDK."""
import argparse,json,hashlib,time
from pathlib import Path
from avancer_agent_relais import charger_agent,sauver_agent,decision_suivante


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False)
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.source,args.observations)}
    a=charger_agent(args.source);b=charger_agent(args.observations)
    debut=time.process_time();records=[]
    for i in range(len(a.actions),args.fin):
        # La suite déjà admise suffit ; cette validation n'appelle aucun chercheur.
        assert any(c.plan and not c.refute for c in a.chaines.values())
        d=decision_suivante(a,args.offre)
        assert d['actions']==[b.actions[i]],(i+1,d['actions'],b.actions[i])
        r=a.observer(b.actions[i],b.images[i+1],b.films[i],b.issues[i],source='trace')
        records.append({'coup':i+1,'resultats':r.get('resultats'),
            'plans':{n:len(c.plan['actions']) if c.plan else None for n,c in a.chaines.items()}})
    journal=[r for r in a.journal if r.get('type')=='suite_apres_reparation']
    validations={n:c.verifier_plan(c.plan['actions']) for n,c in a.chaines.items() if c.plan}
    assert journal and all(v[0] for v in validations.values()) and validations
    assert sources=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.source,args.observations)}
    sauver_agent(a,args.sortie/'agent.pkl')
    rapport={'sdk_actions':0,'recherches':0,'cpu_s':time.process_time()-debut,
        'sources':sources,'sources_inchangees':True,'observations':records,'adoptions':journal,'validations':validations}
    (args.sortie/'rapport.json').write_text(json.dumps(rapport,indent=2,default=str))
    print(json.dumps({'sdk':0,'cpu_s':rapport['cpu_s'],'adoptions':journal},default=str))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('source','observations','sortie'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--fin',type=int,required=True);p.add_argument('--offre',type=int,nargs='+',required=True)
    main(p.parse_args())
