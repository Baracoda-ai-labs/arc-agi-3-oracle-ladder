"""Réexamine un ancien échec après changement du chercheur, sans SDK."""
import argparse,json,time,hashlib
from pathlib import Path
from avancer_agent_relais import charger_agent,sauver_agent
from boucle_agent_integree import empreintes


def preparer(snapshot,sortie,offre,secondes,reexaminer=False):
    sortie.mkdir(parents=True,exist_ok=False)
    avant=snapshot.read_bytes();a=charger_agent(snapshot)
    tranche=len(a.actions)//8
    if reexaminer:
        a.releves_p1.discard(tranche)
        a.journal.append({'type':'reexamen_chercheur_modifie','tranche':tranche,
            'raison':'nouveau_backend_conditionnel_et_priorite_but_herite',
            'aucune_observation_rejouee':True})
    cpu=time.process_time();d=a.decider(offre,secondes=secondes)
    r={'snapshot_sha256':hashlib.sha256(avant).hexdigest(), 'observations':len(a.actions),
       'offre':offre,'decision':d,'cpu_s':time.process_time()-cpu,'actions_sdk':0,
       'sources_sha256':empreintes(), 'source_inchangee':snapshot.read_bytes()==avant}
    assert r['source_inchangee']
    sauver_agent(a,sortie/'agent.pkl')
    (sortie/'decision.json').write_text(json.dumps(r,indent=2,default=int))
    print(json.dumps({'statut':d['statut'],'action':d.get('actions'),
        'modele_plan':d.get('modele_plan'),'suite':len(d.get('suite_plan',[])), 'cpu_s':r['cpu_s']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True);p.add_argument('--offre',type=int,nargs='+',required=True)
    p.add_argument('--secondes',type=float,default=30)
    p.add_argument('--reexaminer',action='store_true')
    a=p.parse_args();preparer(a.snapshot,a.sortie,a.offre,a.secondes,a.reexaminer)
