"""Hypothèse de déplacement sur marqueur avec intermédiaire visuel conservé."""
import numpy as np
from selection_visuelle_immobile import analyser
from contrat_prediction_partielle import contrat_relation,verifier


def apprendre(agent,forme):
    from relation_clic_observee import positions
    f=frozenset(map(tuple,forme));w=max(x for x,y in f)+1;h=max(y for x,y in f)+1
    preuves=[]
    for selection in analyser(agent.images,agent.actions,agent.films,agent.issues):
        k=selection['coup_activation']
        if k>=len(agent.actions) or agent.issues[k]!='continue':continue
        ac=agent.actions[k]
        if not isinstance(ac,(list,tuple)) or ac[0]!='clic':continue
        if not any(abs(c['x']-ac[1])<=1 and abs(c['y']-ac[2])<=1 for c in selection['marqueurs_distants']):continue
        avant=agent.images[k-1];apres=agent.images[k+1]
        aa=positions(avant,f);bb=positions(apres,f);enleves=aa-bb;ajoutes=bb-aa
        if len(enleves)!=1 or len(ajoutes)!=1:continue
        source=next(iter(enleves));dest=next(iter(ajoutes));sx,sy=selection['action_activation'][1:]
        if (sx-source[0],sy-source[1]) not in f:continue
        delta=(dest[0]-source[0],dest[1]-source[1])
        if (delta[0] and delta[1]) or any(v%2 for v in delta):continue
        milieu=tuple((s+d)//2 for s,d in zip(source,dest));x,y=milieu
        motif=np.asarray(avant)[y:y+h,x:x+w]
        if motif.shape!=(h,w) or len(np.unique(motif))<2:continue
        if not np.array_equal(motif,np.asarray(apres)[y:y+h,x:x+w]):continue
        preuves.append({'coup':k+1,'source':list(source),'destination':list(dest),
            'delta':list(delta),'milieu':list(milieu),'motif_intermediaire':motif.tolist(),
            'population_forme_conservee':True,'but_certifie':False,'portee':'hypothese_locale'})
    return preuves


def actualiser(agent,memo):
    attente=getattr(agent,'passage_clic_en_attente',None)
    if attente and len(agent.actions)>attente['index']:
        k=attente['index'];r=verifier(attente['contrat'],agent.images[k],agent.actions[k],agent.images[k+1],agent.issues[k])
        x,y=attente['milieu'];m=np.asarray(attente['motif_intermediaire'])
        r['intermediaire_conserve']=bool(np.array_equal(np.asarray(agent.images[k+1])[y:y+m.shape[0],x:x+m.shape[1]],m)) if agent.issues[k]=='continue' else None
        agent.__dict__.setdefault('validations_passage_clic',[]).append({'coup':k+1,**r})
        agent.passage_clic_en_attente=None
    preuves=apprendre(agent,memo['forme']);agent.memoire_passage_clic={'preuves':preuves,'but_certifie':False}
    return preuves


def proposer_marqueur(agent,memo,selection,marqueurs):
    from relation_clic_observee import positions,candidats
    preuves=actualiser(agent,memo)
    if not preuves:return None
    forme=frozenset(map(tuple,memo['forme']));source=tuple(selection['position']);ps=positions(agent.images[-1],forme)
    w=max(x for x,y in forme)+1;h=max(y for x,y in forme)+1;options=[]
    for preuve in preuves:
        taille=sum(abs(v) for v in preuve['delta']);motif=np.asarray(preuve['motif_intermediaire'])
        variantes=[np.rot90(motif,k) for k in range(4)]+[np.fliplr(np.rot90(motif,k)) for k in range(4)]
        for dx,dy in ((taille,0),(-taille,0),(0,taille),(0,-taille)):
            dest=(source[0]+dx,source[1]+dy);milieu=(source[0]+dx//2,source[1]+dy//2)
            if min(dest)<0 or dest[0]+w>agent.images[-1].shape[1] or dest[1]+h>agent.images[-1].shape[0]:continue
            patch=np.asarray(agent.images[-1])[milieu[1]:milieu[1]+h,milieu[0]:milieu[0]+w]
            if not any(np.array_equal(patch,v) for v in variantes):continue
            cs=[c for c in marqueurs if dest[0]<=c['x']<dest[0]+w and dest[1]<=c['y']<dest[1]+h]
            if not cs:continue
            attendu=(ps-{source})|{dest};repetitions=sum(positions(g,forme)==attendu for g in agent.images)
            options.append((repetitions,-len(candidats(attendu,memo['regle'])),dest,milieu,cs[0],patch,preuve))
    if not options:return None
    _,_,dest,milieu,c,patch,preuve=min(options,key=lambda x:x[:3]);action=['clic',c['x'],c['y']]
    contrat=contrat_relation({'action':action,'forme':memo['forme'],'sources':[list(source)],'destination':list(dest)})
    agent.passage_clic_en_attente={'index':len(agent.actions),'contrat':contrat,'milieu':list(milieu),'motif_intermediaire':patch.tolist()}
    return {'actions':[action],'predictions':[[]],'modeles':[], 'origine':'passage_clic_hypothese_transferee',
        'statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu','contrat_prediction_partielle':contrat,
        'condition_intermediaire':{'position':list(milieu),'pixels':patch.tolist(),'rotation_reflexion':'hypothese_a_verifier'},
        'preuve_source':preuve,'priorite':'etat_formes_non_revisite_puis_interactions_possibles',
        'consommation':'non_affirmee_population_visible_conservee'}
