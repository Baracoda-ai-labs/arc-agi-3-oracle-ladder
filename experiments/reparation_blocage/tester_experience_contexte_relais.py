"""Deux étapes observées au maximum : accès puis expérience, SDK conservé."""
import argparse,copy,hashlib,json,time
from pathlib import Path
import cloudpickle,numpy as np
from avancer_agent_relais import charger_agent,sauver_agent,aligner
from session_sdk_observee import demander
from experience_contexte_alternatif import proposer_experience
from transfert_objets_sans_but import reaffecter
from chaine_agent_integree import canon
from boucle_agent_integree import empreintes
from issues_observees import issue_sdk


def preparer_prediction(c, action):
    c.plan={'actions':[canon(action)],**c.signature(),'origine':'experience_contexte_prospective'}
    c._tracer_plan()


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False)
    debut=time.process_time();a=charger_agent(args.agent)
    etat=demander(args.relais,{'op':'status'});aligner(a,etat)
    principal=copy.deepcopy(next(iter(a.chaines.values())))
    payload=args.modele.read_bytes();meta=json.loads(args.modele.with_suffix('.json').read_text())
    assert hashlib.sha256(payload).hexdigest()==meta['sha256']
    alternatif=cloudpickle.loads(payload)
    with np.load(args.archive.with_suffix('.npz')) as z: gs=list(z['images'])
    acts=[r['action'] for r in json.loads(args.archive.with_suffix('.json').read_text())['rows']]
    hashes=empreintes();(args.sortie/'sources.json').write_text(json.dumps(hashes,indent=2))
    records=[];n0=etat['coups_reels'];sauver_agent(a,args.sortie/'agent.pkl')
    try:
        for _ in range(2):
            d=proposer_experience(principal,alternatif,a.images,a.actions,etat['actions_disponibles'],archives=[(gs,acts)])
            rec={'decision':d,'avant_total':etat['coups_reels']};records.append(rec)
            (args.sortie/'experience.json').write_text(json.dumps(records,indent=2,default=int))
            if not d.get('actions') or etat['termine']:break
            assert empreintes(hashes)==hashes
            c=None
            if d['statut']=='experience_contexte_alternatif':
                c,diag=reaffecter(alternatif,a.images[-1]);assert c is not None
                assert c.rejouer()[1] is not None
                preparer_prediction(c,d['actions'][0])
            a.attente={**d,'modeles':[],'predictions':[[]]};sauver_agent(a,args.sortie/'agent.pkl')
            etat=demander(args.relais,{'op':'play','action':d['actions'][0],
                'image_sha256':etat['image_sha256'],'coup_total_avant':etat['coups_reels'],'purpose':d['statut']})
            trace=Path(etat['trace']);rows=json.loads(trace.with_suffix('.json').read_text())['rows']
            with np.load(trace.with_suffix('.npz')) as z:
                im=z['images'][-1];film=z[f'film_{len(rows)}']
                issue=issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],etat['niveau']-1)
                rec['observation_agent']=a.observer(d['actions'][0],im,film,issue,source='jeu')
                if c is not None:
                    rec['verification_alternative']=c.observer(canon(d['actions'][0]),im,
                        victoire=issue in ('niveau','victoire'),termine=etat['termine'],source='jeu',film=film)
                    a.journal.append({'type':'experience_contexte_verifiee','coup':len(a.actions),
                        'verification':rec['verification_alternative'],'but_suppose':False})
                    data=cloudpickle.dumps(c);p=args.sortie/'candidat_apres.pkl';p.write_bytes(data)
                    p.with_suffix('.json').write_text(json.dumps({'sha256':hashlib.sha256(data).hexdigest()}))
            sauver_agent(a,args.sortie/'agent.pkl')
            (args.sortie/'experience.json').write_text(json.dumps(records,indent=2,default=int))
            if c is not None:break
    finally:
        rapport={'etat_sdk':etat,'actions_nouvelles':etat['coups_reels']-n0,
            'cpu_controleur':time.process_time()-debut,'sources_inchangees':empreintes(hashes)==hashes,
            'limite':'experience composee par harnais, pas encore planificateur multimode integre'}
        (args.sortie/'bilan.json').write_text(json.dumps(rapport,indent=2));print(json.dumps(rapport))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['relais','agent','modele','archive','sortie']:p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
