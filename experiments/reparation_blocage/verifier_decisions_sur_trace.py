"""Validation causale d'un contrôleur sur suffixe archivé, jamais victoire SDK nouvelle."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent,sauver_agent,decision_suivante
from issues_observees import issue_sdk


def verifier(agent_path,trace,offre,baseline,sortie):
    sortie.mkdir(parents=True,exist_ok=False)
    a=charger_agent(agent_path);debut=len(a.actions);cpu=time.process_time()
    rows=json.loads(trace.with_suffix('.json').read_text())['rows'];journal=[]
    with np.load(trace.with_suffix('.npz'),allow_pickle=False) as z:
        if not np.array_equal(a.images,z['images'][:debut+1]):raise ValueError('Prefixe non aligne')
        for i in range(debut,len(rows)):
            d=decision_suivante(a,offre)
            # Écrire la décision avant de fournir l'observation suivante au contrôleur.
            (sortie/f'decision_{i+1}.json').write_text(json.dumps(d,default=int))
            entry={'coup':i+1,'action_proposee':d.get('actions',[]),'action_archive':rows[i]['action']}
            journal.append(entry)
            if d.get('actions')!=[rows[i]['action']]:
                entry['arret']='action_differente_aucune_observation_injectee';break
            issue=issue_sdk(rows[i]['state'],rows[i]['levels_completed'],baseline)
            entry['observation']=a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],issue,source='trace')
            entry['issue_trace']=issue
            if issue!='continue':break
    sauver_agent(a,sortie/'agent.pkl')
    result={'source_agent_sha256':hashlib.sha256(agent_path.read_bytes()).hexdigest(),
        'trace_sha256':{s:hashlib.sha256(trace.with_suffix(s).read_bytes()).hexdigest() for s in ('.json','.npz')},
        'debut':debut,'fin':len(a.actions),'journal':journal,'cpu':time.process_time()-cpu,
        'sdk_actions':0,'preuve':'decisions_et_observations_sur_trace_uniquement'}
    (sortie/'bilan.json').write_text(json.dumps(result,indent=2,default=int))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('agent','trace','sortie'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--offre',type=int,nargs='+',required=True);p.add_argument('--baseline',type=int,required=True)
    v=p.parse_args();r=verifier(v.agent,v.trace,v.offre,v.baseline,v.sortie)
    print(json.dumps({k:r[k] for k in ('debut','fin','cpu','sdk_actions','preuve')}))
