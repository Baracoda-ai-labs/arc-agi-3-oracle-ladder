"""Départager deux tables temporelles existantes sur une région observée."""
import argparse,json,time,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from chrysalide.arc3.films import composantes
from monde_temporel import ajuster,predire
from sonder_animation_distante import preparer
from avancer_agent_relais import charger_agent,sauver_agent,aligner
from session_sdk_observee import demander
from issues_observees import issue_sdk


def contrat(a,source,offre):
    if len(a.actions)<2:raise ValueError('Deux transitions minimales requises')
    action=a.actions[-1]
    p=preparer(a,source,offre,action_cible=action)
    images=list(map(np.asarray,a.images));local=np.zeros(images[-1].shape,bool)
    local[tuple(np.array(p['local_yx']).T)]=True
    from objets_identites import occurrences
    coque=source.modele_gagnant.perception.coque
    h,w=np.asarray(coque).shape
    for g in images:
        for x,y in occurrences(g,coque):local[y:y+h,x:x+w]=True
    hud=source.modele_gagnant.perception.hud
    change=np.zeros(local.shape,bool)
    for b,g in zip(images,images[1:]):change|=b!=g
    for y,x in hud:change[y,x]=False
    change&=~local
    classes=set()
    # Couples de couleurs présents avant ET après les transitions distantes.
    for b,g in zip(images,images[1:]):
        m=(b!=g)&change
        classes |= set(map(int,np.unique(b[m]))) & set(map(int,np.unique(g[m])))
    if len(classes)<2:raise ValueError('Classes changeantes non isolées')
    region=np.zeros(local.shape,bool)
    for g in images:
        for comp in composantes(np.isin(g,list(classes))&~local):
            if any(change[y,x] for x,y in comp):
                for x,y in comp:region[y,x]=True
    for y,x in hud:region[y,x]=False
    essais=[]
    for couleur in sorted(classes):
        compte=[int(np.count_nonzero(g[region]==couleur)) for g in images]
        transitions=[(i+1,act,compte[i+1]-compte[i]) for i,act in enumerate(a.actions)]
        modeles=ajuster(transitions);prevision=predire(modeles,SimpleNamespace(haut=compte[-1]),action,len(a.actions)+1)
        valeurs=prevision['predictions']
        if (prevision['couvert'] and valeurs and
                all(0 <= v <= int(region.sum()) for v in valeurs.values()) and
                any(v != compte[-1] for v in valeurs.values())):
            essais.append({'classe_observee':couleur,'comptes':compte,'modeles':modeles,'prevision':prevision})
    if not essais:raise ValueError('Aucune évolution observable couverte dans la région')
    return {'action':action,'local_yx':p['local_yx'],'prediction_locale':p['prediction_locale'],
        'deplacement_local':p['deplacement_local'],'region_yx':np.argwhere(region).tolist(),'essais':essais,
        'hypotheses_exhaustives':False,'causalite_certifiee':False,'but_inconnu':True,
        'portee':'comptes dans supports changeants observés, pas rendu global ni périodicité démontrée'}


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False);t=time.process_time()
    a=charger_agent(args.agent);source=charger_agent(args.source)
    etat=demander(args.relais,{'op':'status'});aligner(a,etat)
    p=contrat(a,source,etat['actions_disponibles']);p['sha_source']=hashlib.sha256(args.agent.read_bytes()).hexdigest()
    (args.sortie/'prediction_avant.json').write_text(json.dumps(p,indent=2))
    if not args.executer:return
    a.attente={'actions':[p['action']],'modeles':[],'predictions':[[]],'statut':'experience_phase_observee','contrat_partiel':p}
    sauver_agent(a,args.sortie/'agent.pkl')
    apres=demander(args.relais,{'op':'play','action':p['action'],'image_sha256':etat['image_sha256'],
        'coup_total_avant':etat['coups_reels'],'purpose':'experience_phase_observee'})
    tr=Path(apres['trace']);rows=json.loads(tr.with_suffix('.json').read_text())['rows']
    with np.load(tr.with_suffix('.npz')) as z:
        image=z['images'][-1];film=z[f'film_{len(rows)}'];ij=tuple(np.array(p['local_yx']).T);roi=tuple(np.array(p['region_yx']).T)
        resultats=[]
        for h in p['essais']:
            n=int(np.count_nonzero(image[roi]==h['classe_observee']))
            resultats.append({'classe':h['classe_observee'],'compte_observe':n,
                'compatibles':[nom for nom,v in h['prevision']['predictions'].items() if v==n]})
        obs={'pixels_ecart_locaux':int(np.count_nonzero(image[ij]!=p['prediction_locale'])),
            'resultats':resultats,'causalite_certifiee':False,'frames':len(film)}
        obs['agent']=a.observer(p['action'],image,film,issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],apres['niveau']-1))
    a.journal.append({'type':'experience_phase_observee','coup':len(a.actions),'preuve':p,'observation':obs})
    sauver_agent(a,args.sortie/'agent.pkl');(args.sortie/'observation.json').write_text(json.dumps(obs,indent=2,default=int))
    b={'etat_sdk':apres,'actions_nouvelles':apres['coups_reels']-etat['coups_reels'],'cpu_controleur':time.process_time()-t,**{k:v for k,v in obs.items() if k!='agent'}}
    (args.sortie/'bilan.json').write_text(json.dumps(b,indent=2));print(json.dumps(b))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('agent','source','relais','sortie'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--executer',action='store_true');main(p.parse_args())
