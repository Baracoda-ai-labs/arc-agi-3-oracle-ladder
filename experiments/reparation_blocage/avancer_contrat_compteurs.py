"""Progression locale sous compteurs provisoires ; arrêt avant saturation non simulée."""
import argparse,json,time
from pathlib import Path
import numpy as np
from compteurs_regions_observees import apprendre,prevoir
from sonder_animation_distante import preparer
from objets_identites import occurrences
from avancer_agent_relais import charger_agent,sauver_agent,aligner
from session_sdk_observee import demander
from issues_observees import issue_sdk


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False);t=time.process_time()
    a=charger_agent(args.agent);source=charger_agent(args.source);roi=json.loads(args.region.read_text())
    classes=[h['classe_observee'] for h in roi['essais']]
    etat=demander(args.relais,{'op':'status'});aligner(a,etat);n=etat['coups_reels'];journal=[]
    for _ in range(args.coups):
        h=apprendre(a.images,a.films,a.actions,roi['region_yx'],classes)
        # Continuer une commande effectivement observée qui progresse localement.
        action=a.actions[-1];p=preparer(a,source,etat['actions_disponibles'],action_cible=action)
        pred=prevoir(h,action);k=len(a.actions)+1
        proof={'hypotheses':h,'prediction_compteurs':pred,'deplacement_local':p['deplacement_local'],'action':action,
            'but_inconnu':True,'modele_global_admis':False,'face_locale_non_validee':True}
        (args.sortie/f'prediction_{k:05}.json').write_text(json.dumps(proof,indent=2,default=int))
        if pred is None:break
        local=set(map(tuple,p['local_yx']))
        saturations=[hyp for hyp,q in zip(h,pred) if q['saturation_attendue']]
        if any(local & set(map(tuple,hyp['enveloppe_saturation_observee_yx'])) for hyp in saturations):break
        proof['saturation_distante_sans_contact_selon_enveloppe_observee']=bool(saturations)
        (args.sortie/f'prediction_{k:05}.json').write_text(json.dumps(proof,indent=2,default=int))
        before=occurrences(a.images[-1],source.modele_gagnant.perception.coque)
        if len(before)!=1:break
        if not args.executer:break
        a.attente={'actions':[action],'modeles':[],'predictions':[[]],'statut':'experience_compteurs_partiels','contrat_partiel':proof}
        sauver_agent(a,args.sortie/'agent.pkl')
        etat=demander(args.relais,{'op':'play','action':action,'image_sha256':etat['image_sha256'],
            'coup_total_avant':etat['coups_reels'],'purpose':'experience_compteurs_partiels'})
        tr=Path(etat['trace']);rows=json.loads(tr.with_suffix('.json').read_text())['rows']
        with np.load(tr.with_suffix('.npz')) as z:
            image=z['images'][-1];film=z[f'film_{len(rows)}'];after=occurrences(image,source.modele_gagnant.perception.coque)
            local=(len(after)==1 and list(np.array(after[0])-before[0])==p['deplacement_local'])
            comptes=[]
            for q in pred:
                ij=tuple(np.array(q['region_yx']).T);v=int(np.count_nonzero(image[ij]==q['classe']))
                comptes.append({'classe':q['classe'],'predite':q['compte'],'observee':v,'exact':v==q['compte']})
            obs={'coup':k,'position_locale_exacte':bool(local),'comptes':comptes,'frames':len(film),'rendu_complet_valide':False}
            obs['agent']=a.observer(action,image,film,issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],etat['niveau']-1))
        a.journal.append({'type':'experience_compteurs_partiels','preuve':proof,'observation':obs});journal.append(obs)
        sauver_agent(a,args.sortie/'agent.pkl');(args.sortie/f'observation_{k:05}.json').write_text(json.dumps(obs,indent=2,default=int))
        if not local or not all(q['exact'] for q in comptes) or etat['termine']:break
    b={'etat_sdk':etat,'actions_nouvelles':etat['coups_reels']-n,'cpu_controleur':time.process_time()-t,
        'journal':[ {k:v for k,v in x.items() if k!='agent'} for x in journal]}
    (args.sortie/'bilan.json').write_text(json.dumps(b,indent=2,default=int));print(json.dumps(b,default=int))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('agent','source','relais','sortie','region'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--coups',type=int,default=3);p.add_argument('--executer',action='store_true');main(p.parse_args())
