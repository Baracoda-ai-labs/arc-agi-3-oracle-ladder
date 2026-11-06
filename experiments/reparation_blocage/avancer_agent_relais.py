"""Contrôleur remplaçable ; le propriétaire SDK reste dans son processus."""
import argparse,json,hashlib,time
from pathlib import Path
import cloudpickle,numpy as np
from session_sdk_observee import demander,empreinte_image
from boucle_agent_integree import empreintes
from issues_observees import issue_sdk


def sauver_agent(agent,path):
    payload=cloudpickle.dumps(agent);tmp=path.with_suffix('.tmp');tmp.write_bytes(payload);tmp.replace(path)
    path.with_suffix('.json').write_text(json.dumps({'sha256':hashlib.sha256(payload).hexdigest(),
        'actions':len(agent.actions),'image_sha256':empreinte_image(agent.images[-1])},indent=2))


def charger_agent(path):
    payload=path.read_bytes();meta=json.loads(path.with_suffix('.json').read_text())
    if hashlib.sha256(payload).hexdigest()!=meta['sha256']:raise ValueError('Agent modifié sans empreinte')
    return cloudpickle.loads(payload)


def aligner(agent,etat):
    trace=Path(etat['trace']);j=json.loads(trace.with_suffix('.json').read_text());rows=j['rows']
    with np.load(trace.with_suffix('.npz')) as z:
        n=len(agent.actions)
        if len(rows)==n+1 and agent.attente and rows[-1]['action']==agent.attente['actions'][0]:
            # Reprise après coup joué mais avant sauvegarde du contrôleur.
            agent.observer(rows[-1]['action'],z['images'][-1],z[f'film_{len(rows)}'],
                issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],etat['niveau']-1))
            n+=1
        if n!=len(rows) or not np.array_equal(agent.images,z['images']):
            raise ValueError('Contrôleur et historique SDK désalignés')
    if empreinte_image(agent.images[-1])!=etat['image_sha256']:raise ValueError('État courant différent')


def divergence_plan(decision, observation):
    owner=decision.get('modele_plan')
    resultats = observation.get('resultats', [])
    confirmes = ('transition_confirmee','victoire_reelle','victoire_verifiee_sur_trace')
    if owner:
        return any(r.get('nom') == owner and r.get('statut') not in confirmes for r in resultats)
    # Les expériences ont aussi des prédictions ; ne pas perdre leur réfutation.
    return bool(resultats) and all(r.get('statut') not in confirmes for r in resultats)


def decision_suivante(agent,offre):
    if agent.attente and agent.attente.get('actions'):
        d=agent.attente
        owner=d.get('modele_plan')
        if owner:
            from chaine_agent_integree import canon
            c=agent.chaines.get(owner)
            plan=[canon(d['actions'][0]),*d.get('suite_plan',[])]
            if c is None or c.refute or not c.verifier_plan(plan)[0]:
                raise ValueError('Decision sauvegardee non validee depuis etat courant')
        return d
    return agent.decider(offre,secondes=30)


def avancer(relais,path,sortie,coups,arreter_ecart=False):
    sortie.mkdir(parents=True,exist_ok=False);cpu=time.process_time();a=charger_agent(path)
    etat=demander(relais,{'op':'status'});aligner(a,etat);sauver_agent(a,path)
    sources=empreintes();(sortie/'sources.json').write_text(json.dumps(sources,indent=2));journal=[]
    try:
        for _ in range(coups):
            if etat['termine']:break
            if empreintes(sources)!=sources:raise ValueError('Code changé pendant lot ; SDK conservé')
            k=len(a.actions)+1;d=decision_suivante(a,etat['actions_disponibles'])
            entry={'coup':k,'decision':d};journal.append(entry)
            (sortie/f'decision_{k:05}.json').write_text(json.dumps(d,default=int))
            sauver_agent(a,path)
            if not d.get('actions'):break
            etat=demander(relais,{'op':'play','action':d['actions'][0],
                'image_sha256':etat['image_sha256'],'coup_total_avant':etat['coups_reels'],'purpose':d['statut']})
            trace=Path(etat['trace']);rows=json.loads(trace.with_suffix('.json').read_text())['rows']
            with np.load(trace.with_suffix('.npz')) as z:
                entry['observation']=a.observer(d['actions'][0],z['images'][-1],z[f'film_{len(rows)}'],
                    issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],etat['niveau']-1))
            sauver_agent(a,path)
            (sortie/f'observation_{k:05}.json').write_text(json.dumps(entry['observation'],default=int))
            (sortie/'journal.json').write_text(json.dumps(journal,default=int))
            if arreter_ecart and divergence_plan(d,entry['observation']):
                break  # observation et état conservés, réparation au prochain appel
    finally:
        (sortie/'bilan.json').write_text(json.dumps({'etat_sdk':etat,'cpu_controleur':time.process_time()-cpu,
            'actions_nouvelles':sum('observation' in e for e in journal),'code_inchange':empreintes(sources)==sources,
            'arret_sur_ecart_plan':bool(arreter_ecart and journal and divergence_plan(journal[-1]['decision'],journal[-1].get('observation',{})))},indent=2))
    return etat

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--relais',type=Path,required=True);p.add_argument('--agent',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True);p.add_argument('--coups',type=int,default=1)
    p.add_argument('--arreter-ecart',action='store_true');a=p.parse_args()
    print(json.dumps(avancer(a.relais,a.agent,a.sortie,a.coups,a.arreter_ecart)))
