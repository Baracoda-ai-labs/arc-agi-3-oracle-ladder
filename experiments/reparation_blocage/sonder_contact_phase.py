"""Contact inédit avec une région à phase observée, sans loi de collision imposée."""
import argparse,json,time
from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent,sauver_agent,aligner
from compteurs_regions_observees import apprendre,prevoir
from session_sdk_observee import demander
from issues_observees import issue_sdk


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False);t=time.process_time()
    a=charger_agent(args.agent);s=charger_agent(args.source).modele_gagnant.perception
    base=getattr(s,'source',s);roi=json.loads(args.region.read_text())
    etat=demander(args.relais,{'op':'status'});aligner(a,etat)
    h=apprendre(a.images,a.films,a.actions,roi['region_yx'],[q['classe_observee'] for q in roi['essais']])
    positions=base.positions(s.vue(a.images[-1]));assert len(positions)==1
    x,y=positions[0];hh,ww=base.coque.shape
    occ=set(map(tuple,roi['region_yx']));choix=[]
    for code,(dx,dy) in sorted(base.mouvements.items()):
        if code not in etat['actions_disponibles']:continue
        if any(code==act and base.positions(s.vue(im))==positions for im,act in zip(a.images,a.actions)):continue
        touche={(yy,xx) for yy in range(y+dy,y+dy+hh) for xx in range(x+dx,x+dx+ww)}&occ
        pred=prevoir(h,code)
        if touche and pred and not any(q['saturation_attendue'] for q in pred):choix.append((code,dx,dy,pred))
    if not choix:raise ValueError('Aucun contact nouveau couvert hors saturation')
    code,dx,dy,pred=choix[0]
    preuve={'action':code,'position_avant':[x,y],'alternatives_position':{'blocage':[x,y],'passage':[x+dx,y+dy]},
        'prediction_compteurs':pred,'causalite_certifiee':False,'alternatives_exhaustives':False,'but_inconnu':True}
    (args.sortie/'prediction_avant.json').write_text(json.dumps(preuve,indent=2,default=int))
    if not args.executer:return
    a.attente={'actions':[code],'modeles':[],'predictions':[[]],'statut':'experience_contact_phase','contrat_partiel':preuve};sauver_agent(a,args.sortie/'agent.pkl')
    etat=demander(args.relais,{'op':'play','action':code,'image_sha256':etat['image_sha256'],'coup_total_avant':etat['coups_reels'],'purpose':'experience_contact_phase'})
    tr=Path(etat['trace']);rows=json.loads(tr.with_suffix('.json').read_text())['rows']
    with np.load(tr.with_suffix('.npz')) as z:
        image=z['images'][-1];film=z[f'film_{len(rows)}'];pos=base.positions(s.vue(image));comptes=[]
        for q in pred:
            ij=tuple(np.array(q['region_yx']).T);v=int(np.count_nonzero(image[ij]==q['classe']));comptes.append({'predite':q['compte'],'observee':v,'exact':v==q['compte']})
        obs={'positions_observees':pos,'compatibles':[n for n,p in preuve['alternatives_position'].items() if len(pos)==1 and list(pos[0])==p],'comptes':comptes,'frames':len(film),'modele_global_admis':False}
        obs['agent']=a.observer(code,image,film,issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],etat['niveau']-1))
    a.journal.append({'type':'experience_contact_phase','preuve':preuve,'observation':obs});sauver_agent(a,args.sortie/'agent.pkl')
    (args.sortie/'observation.json').write_text(json.dumps(obs,indent=2,default=int));b={'etat_sdk':etat,'actions_nouvelles':1,'cpu_controleur':time.process_time()-t,**{k:v for k,v in obs.items() if k!='agent'}}
    (args.sortie/'bilan.json').write_text(json.dumps(b,indent=2,default=int));print(json.dumps(b,default=int))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('agent','source','region','relais','sortie'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--executer',action='store_true');main(p.parse_args())
