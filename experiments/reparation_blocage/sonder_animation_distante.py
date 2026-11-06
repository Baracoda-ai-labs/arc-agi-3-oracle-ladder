"""Contrastes partiels sur un film observé ; aucune loi ni cible de jeu injectée."""
import argparse,copy,hashlib,json,time
from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent,sauver_agent,aligner
from session_sdk_observee import demander
from session_chaine_generique import agent_transfere
from chaine_agent_integree import canon
from issues_observees import issue_sdk


def preparer(agent,source,offre,action_cible=None):
    if not agent.actions or not agent.films:raise ValueError('Un premier film requis')
    transfert=agent_transfere(source,agent.images[-1],offre)
    c=next(iter(transfert.chaines.values()));check,etat=c.rejouer()
    if etat is None:raise ValueError('Instance non rendue exactement')
    pc,scene=etat;pieces=[o for o in scene.sprites if 'piece' in o.get('tags',[])]
    if len(pieces)!=1:raise ValueError('Contraste local ambigu : une pièce requise')
    p=pieces[0];h,w=p['pixels'].shape
    masque=np.zeros(np.asarray(agent.images[-1]).shape,bool)
    masque[max(0,p['y']-h):p['y']+2*h,max(0,p['x']-w):p['x']+2*w]=True
    initial=np.asarray(agent.images[0]);film=np.asarray(agent.films[0]);courant=np.asarray(agent.images[-1])
    distant=np.any(film!=initial,axis=0)&~masque
    for y,x in c.perception.hud:distant[y,x]=False
    if not distant.any():raise ValueError('Aucune variation distante séparée')
    mouvements=c.perception.source.mouvements
    for action in sorted(set(offre)&set(mouvements)):
        if action_cible is not None and action!=action_cible:continue
        if action_cible is None and action==agent.actions[-1]:continue
        sc=copy.deepcopy(scene);pc.step(sc,canon(action))
        mobiles=[o for o in sc.sprites if 'piece' in o.get('tags',[])]
        q=mobiles[0]
        if (q['x'],q['y'])==(p['x'],p['y']):continue
        local=np.zeros(courant.shape,bool)
        for o in (p,q):
            hh,ww=o['pixels'].shape;local[o['y']:o['y']+hh,o['x']:o['x']+ww]=True
        if np.any(local&distant):continue
        pred=c.perception.rendu(sc)
        return {'action':action,'origine':'commande_heritee_distincte_avec_deplacement_simule',
            'deplacement_local':[q['x']-p['x'],q['y']-p['y']],
            'local_yx':np.argwhere(local).tolist(),'prediction_locale':pred[local].tolist(),
            'distant_yx':np.argwhere(distant).tolist(),'inertie_distante':courant[distant].tolist(),
            'film_repetition_distante':[f[distant].tolist() for f in film],
            'hypotheses':['animation identique à commande différente','inertie distante',
                'autre évolution dépendante de phase/état/commande non départagés'],
            'modele_complet_admis':False,'but_inconnu':True,'controle_instance':check}
    raise ValueError('Aucune commande héritée nouvelle à effet local simulé sans recouvrement')


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False);t=time.process_time()
    a=charger_agent(args.agent);source=charger_agent(args.source)
    etat=demander(args.relais,{'op':'status'});aligner(a,etat)
    preuve=preparer(a,source,etat['actions_disponibles'])
    preuve['sha_source_agent']=hashlib.sha256(args.agent.read_bytes()).hexdigest()
    (args.sortie/'prediction_avant.json').write_text(json.dumps(preuve,indent=2))
    if not args.executer:return
    a.attente={'actions':[preuve['action']],'modeles':[],'predictions':[[]],
        'statut':'experience_animation_distante','contrat_partiel':preuve,'but':'inconnu'}
    sauver_agent(a,args.sortie/'agent.pkl')
    apres=demander(args.relais,{'op':'play','action':preuve['action'],'image_sha256':etat['image_sha256'],
        'coup_total_avant':etat['coups_reels'],'purpose':'experience_animation_distante'})
    trace=Path(apres['trace']);rows=json.loads(trace.with_suffix('.json').read_text())['rows']
    with np.load(trace.with_suffix('.npz')) as z:
        image=z['images'][-1];film=z[f'film_{len(rows)}']
        local=tuple(np.array(preuve['local_yx']).T);distant=tuple(np.array(preuve['distant_yx']).T)
        observation={'local_exact':bool(np.array_equal(image[local],preuve['prediction_locale'])),
            'pixels_ecart_locaux':int(np.count_nonzero(image[local]!=preuve['prediction_locale'])),
            'inertie_distante_finale':bool(np.array_equal(image[distant],preuve['inertie_distante'])),
            'repetition_distante_film_exacte':bool(np.array_equal([f[distant].tolist() for f in film],preuve['film_repetition_distante'])),
            'film_distant_observe':[f[distant].tolist() for f in film],
            'causalite_commande_certifiee':False,'modele_complet_admis':False}
        observation['agent']=a.observer(preuve['action'],image,film,issue_sdk(rows[-1]['state'],rows[-1]['levels_completed'],apres['niveau']-1))
    a.journal.append({'type':'experience_animation_distante','coup':len(a.actions),'preuve':preuve,'observation':observation})
    sauver_agent(a,args.sortie/'agent.pkl')
    (args.sortie/'observation.json').write_text(json.dumps(observation,indent=2,default=int))
    bilan={'etat_sdk':apres,'actions_nouvelles':apres['coups_reels']-etat['coups_reels'],'cpu_controleur':time.process_time()-t,
        **{k:v for k,v in observation.items() if k not in ('agent','film_distant_observe')}}
    (args.sortie/'bilan.json').write_text(json.dumps(bilan,indent=2));print(json.dumps(bilan))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('agent','source','relais','sortie'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--executer',action='store_true');main(p.parse_args())
