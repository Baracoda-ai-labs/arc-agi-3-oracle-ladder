"""Même agent, propriétaire SDK persistant ; lots de travail sans plafond à80."""
import argparse,json,os,sys,time,resource
from pathlib import Path
import numpy as np
from boucle_agent_integree import AUTORISES,empreintes
from boucle_objets_variables import LaboP1
from chaine_agent_integree import AgentIntegre
from issues_observees import issue_sdk

def configurer_composition(agent, activation=None, ancien=None):
    """Option explicite ou héritage du flag seul ; aucune banque d'épisodes créée."""
    source = ancien if ancien is not None else agent
    actif = bool(getattr(source, 'composition_contextuelle_auto', False)) if activation is None else bool(activation)
    agent.composition_contextuelle_auto = actif
    return actif

def configurer_recherche(agent, activation=None, ancien=None, workers=None):
    source=ancien if ancien is not None else agent
    n=getattr(source,'recherche_prolongee_workers',2) if workers is None else workers
    if n not in (1,2):raise ValueError('Un ou deux workers requis')
    agent.recherche_prolongee_workers=n
    agent.recherche_prolongee=bool(getattr(source,'recherche_prolongee',False)) if activation is None else bool(activation)
    return agent.recherche_prolongee


def observations_tentatives(ancien):
    """Épisodes observés séparés ; aucune transition de RESET ni théorie importée."""
    import copy
    if len(ancien.images) != len(ancien.actions)+1 or len(ancien.issues) != len(ancien.actions):
        raise ValueError('Episode non aligne')
    if any(isinstance(a, int) and a == 0 for a in ancien.actions):
        raise ValueError('RESET ne doit pas entrer dans les observations du modele')
    episodes = copy.deepcopy(getattr(ancien, 'observations_episodes', []))
    from memoire_observations import episode_observe
    episodes.append(episode_observe(ancien.images, ancien.actions, ancien.issues,
                                   getattr(ancien, 'films', None)))
    return episodes


def lire_graine(source, bilan):
    etat=source/'etat.json'
    if etat.exists():
        bilan['graine_exploration']=json.loads(etat.read_text()).get('graine_exploration',0)
    return bilan.get('graine_exploration',0)


def restaurer_agent(source, limite=sys.maxsize):
    z=np.load(source/'N1/partie.npz')
    rows=json.loads((source/'N1/partie.json').read_text())['rows']
    bilan=json.loads((source/'bilan.json').read_text())
    graine=lire_graine(source,bilan)
    flags={k:bilan.get(k,False) for k in ('decouverte_courte','legacy_sans_but',
      'utilite_sondes','exploration_p1','routage_classes','aiguillage_provisoire',
      'revision_solidite','revision_projection','dreamcoder_mots')}
    if flags['decouverte_courte'] or len(rows)<8:
        raise ValueError('Restauration initiale huit sondes requise par ce raccord')
    a=AgentIntegre(z['images'][:9],[r['action'] for r in rows[:8]],
      [z[f'film_{i+1}'] for i in range(8)],['continue']*8,limite=limite,graine_exploration=graine,**flags)
    for i in range(8,len(rows)):
        if a.reconstruction:a.reconstruire()
        d={'actions':[rows[i]['action']],'predictions':[[]]}
        a._suivre_experience(d);a.attente=d
        a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],
                   issue_sdk(rows[i]['state'],rows[i]['levels_completed'],0))
    original=json.loads((source/'journal.json').read_text())
    dernier=next(e for e in reversed(original) if e['type']=='observation')
    if set(a.chaines)!=set(dernier['modeles_survivants']):
        raise ValueError('Modèles reconstruits différents : ne pas prétendre même agent')
    for c in a.chaines.values():
        assert c.rejouer()[1] is not None
    a.releves_p1={i//8 for i in range(8,len(rows))}
    a.journal=original
    return a,z,rows,bilan


def nouvel_agent(images, actions, films, issues, graine_exploration=0):
    agent = AgentIntegre(images, actions, films, issues, limite=sys.maxsize,
        legacy_sans_but=True, utilite_sondes=True, exploration_p1=True,
        aiguillage_provisoire=True, revision_solidite=True,
        revision_projection=True, couverture_commandes=True, graine_exploration=graine_exploration,
        boucle_reparation=os.environ.get("CHRYS_BOUCLE_AGENT", "0") == "1",
        budget_sondes_reparation=int(os.environ.get("CHRYS_BOUCLE_AGENT_SONDES", "3")))
    agent.recherche_prolongee = False
    return agent


def reconstituer_gagnant(source, prefixe=None):
    z=np.load(source/'N1/partie.npz')
    rows=json.loads((source/'N1/partie.json').read_text())['rows']
    b=json.loads((source/'bilan.json').read_text())
    graine=lire_graine(source,b)
    snapshot=source/'modele_gagnant_local.pkl'
    if snapshot.exists() and snapshot.with_suffix('.json').exists():
        import cloudpickle,hashlib
        from chaine_agent_integree import lots,canon
        meta=json.loads(snapshot.with_suffix('.json').read_text())
        if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Mémoire gagnante altérée')
        c=cloudpickle.loads(snapshot.read_bytes())
        if not np.array_equal(c.grilles,z['images'][:-1]) or c.lots!=lots([r['action'] for r in rows[:-1]]):
            raise ValueError('Mémoire gagnante du mauvais préfixe')
        if c.rejouer()[1] is None or not c.verifier_plan([canon(rows[-1]['action'])])[0]:
            raise ValueError('Mémoire gagnante non vérifiable')
        if rows[-1]['levels_completed']<1:raise ValueError('Victoire réelle absente')
        a=nouvel_agent(z['images'],[r['action'] for r in rows],
            [z[f'film_{i+1}'] for i in range(len(rows))],['continue']*(len(rows)-1)+['niveau'])
        a.graine_exploration=graine
        a.modele_gagnant=c
        return a,z,rows,b
    if prefixe is not None:
        a,zp,rp=agent_prefixe(prefixe)
        debut=len(rp)
        if not np.array_equal(z['images'][:debut+1],zp['images']):
            raise ValueError('Préfixe gagnant incompatible')
    else:
        debut=8
        a=nouvel_agent(z['images'][:9],[r['action'] for r in rows[:8]],
            [z[f'film_{i+1}'] for i in range(8)],['continue']*8)
    a.graine_exploration=graine
    for i in range(debut,len(rows)):
        d=a.decider(b['actions_disponibles'],secondes=30)
        if d.get('actions') != [rows[i]['action']]:
            raise ValueError(f'Reconstruction décision différente au {i+1}')
        a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],
            issue_sdk(rows[i]['state'],rows[i]['levels_completed'],0))
    if a.modele_gagnant is None:raise ValueError('Aucun modèle gagnant conservé')
    return a,z,rows,b


def agent_transfere(ancien, image, offre):
    from transfert_modele_c import reaffecter
    from transfert_roles import reaffecter as reaffecter_roles
    from selection_observee import SelectionObservee
    from chaine_agent_integree import NOMS
    if ancien.modele_gagnant is None:
        if not ancien.issues or ancien.issues[-1] not in ('niveau','victoire'):
            raise ValueError('Victoire réelle absente pour transfert de mémoire partielle')
        from relation_clic_observee import memoire_transferee
        refus_relation=None
        try:memoire=memoire_transferee(ancien,image)
        except ValueError as exc:
            memoire=None;refus_relation=str(exc)
        a=nouvel_agent([image],[],[],[],graine_exploration=getattr(ancien,'graine_exploration',0))
        configurer_composition(a, ancien=ancien)
        configurer_recherche(a, ancien=ancien)
        a.memoire_relation_clic=memoire
        from memoire_transfert_partiel import conserver
        conserver(ancien,a)
        a.commandes_connues=set(ancien.commandes_connues)|{x for x in ancien.actions if isinstance(x,int)}
        # La relation transférée ne couvre que les clics. Une touche inerte dans
        # l'ancien contexte n'est pas prouvée inactive au niveau suivant.
        a.sondes_contexte=[k for k in offre if k in (1,2,3,4,5,7)]
        a.journal.append({'type':'transfert_memoire_partielle','but_certifie':False,
            'modele_complet':False,'regle_provisoire':memoire,'victoire_source_observee':True,
            'relation_non_transferee':refus_relation,
            'commandes_non_couvertes_a_verifier':a.sondes_contexte.copy(),
            'historique_commandes_pas_preuve_inertie_globale':True})
        return a
    sources={'gagnant':ancien.modele_gagnant}
    preuve=next((e for e in reversed(getattr(ancien,'journal',[]))
                 if e.get('type')=='memoire_issue_observee'),None)
    if preuve:
        confirmes={p['nom'] for p in preuve.get('candidats',[]) if p.get('but_confirme_par_prediction')}
        portefeuille={n:c for n,c in getattr(ancien,'modeles_avant_victoire',{}).items() if n in confirmes}
        if portefeuille:sources=portefeuille
    chaines={};diagnostics=[]
    for label,source_candidate in sources.items():
        transfert_roles=isinstance(source_candidate.perception,SelectionObservee)
        operation=reaffecter_roles if transfert_roles else reaffecter
        try:
            c,diag=operation(source_candidate,image,[(NOMS[x],) for x in offre if x in NOMS],reserve=sys.maxsize)
        except ValueError as exc:
            diagnostics.append({'type':'transfert_candidat_refuse','source':label,'raison':str(exc)})
            continue
        if hasattr(c,'preuve_transfert_roles'):
            c.preuve_transfert_roles['but_source_confirme_par_victoire']=True
            c.preuve_transfert_roles['source_portefeuille']=label
        nom='transfert_roles' if transfert_roles else 'transfert_modele_c'
        if len(sources)>1:nom+='/'+label
        chaines[nom]=c;diagnostics.append({'type':nom,'source':label,**diag})
    if not chaines:raise ValueError('Aucun modèle confirmé transférable : '+repr(diagnostics))
    c=next(iter(chaines.values()))
    a=nouvel_agent([image],[],[],[], graine_exploration=getattr(ancien, "graine_exploration", 0))
    configurer_composition(a, ancien=ancien)
    configurer_recherche(a, ancien=ancien)
    from chaine_agent_integree import lots
    source=ancien.modele_gagnant
    import copy
    # Hériter la théorie réaffectée et vérifiée, pas le cache de recherche source.
    a.theorie_precedente=copy.deepcopy(getattr(c.perception,'th_releve',None))
    a.precedents=list(ancien.precedents)+[{'grilles':source.grilles,
        'lots':source.lots,'finale':lots([ancien.actions[-1]])[0],
        'films':[e['images'].tolist() if e else None for e in source.films.entrees]}]
    a.commandes_connues=ancien.commandes_connues | {x for x in ancien.actions if isinstance(x,int)}
    from memoire_transfert_partiel import conserver
    conserver(ancien,a)
    a.chaines=chaines;a.reconstruction=False
    a.journal.extend(diagnostics)
    a.journal.append({'type':'portefeuille_transfere','candidats_confirmes':len(sources),
                      'admis':list(chaines),'regles_reapprises':0})
    return a


def agent_prefixe(path):
    from representation_legacy_sans_but import construire
    from chaine_agent_integree import sdk
    h=json.loads(path.read_text())
    actions=[sdk((l['actions'][0]['action'], l['actions'][0]['row'], l['actions'][0]['col']))
             if l['actions'][0]['action']=='MOUSE' else sdk((l['actions'][0]['action'],))
             for l in h['lots']]
    a=nouvel_agent(h['grilles'],actions,h['films'],['continue']*len(actions))
    c,diag=construire(h)
    if not diag['admis']:raise ValueError('Préfixe sans modèle admis')
    c.activer_atms()
    a.chaines={'perception_sans_but_legacy':c};a.reconstruction=False
    a.journal.append({'type':'modele_prefixe_reutilise','controle':diag})
    z={'images':np.asarray(h['grilles']),**{f'film_{i+1}':np.asarray(f) for i,f in enumerate(h['films'])}}
    return a,z,[{'action':act} for act in actions]

def cpu_enfants():
    """CPU des enfants terminés et récoltés ; exclut les enfants encore actifs."""
    r=resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime+r.ru_stime


def metadonnees_graine(graine):
    return {'graine_exploration':graine, 'sdk_seed_appliquee':False,
            'graine_portee':'P1 reconstruit sur prefixe ; graine fixe sans increment de tentative',
            'pythonhashseed':os.environ.get('PYTHONHASHSEED')}


def entier_positif(valeur, nom):
    if isinstance(valeur,bool) or not isinstance(valeur,int) or valeur<1:
        raise ValueError(f'{nom} doit être un entier positif')
    return valeur


def piloter_auto(laboratoire, avancer, niveau_suivant, *, lots=1, coups=32, retenter=None):
    """Lots de travail reprenables ; aucune limite interprétée comme défaite."""
    lots=entier_positif(lots,'lots');coups=entier_positif(coups,'coups')
    for _ in range(lots):
        lab=laboratoire()
        if lab.partie_gagnee:return 'jeu_gagne'
        if lab.finished and not lab.won:
            if retenter is None:return 'defaite_sdk'
            retenter()
            lab=laboratoire()
            if lab.partie_gagnee:return 'jeu_gagne'
            if lab.finished and not lab.won:return 'defaite_sdk'
        if lab.won:niveau_suivant()  # une ambiguïté de transfert remonte sans reset
        resultat=avancer(coups)
        lab=laboratoire()
        if lab.partie_gagnee:return 'jeu_gagne'
        if lab.finished and not lab.won:
            if retenter is None:return 'defaite_sdk'
            continue  # le prochain lot conserve le diagnostic puis relance un épisode
        if not lab.won and resultat not in ('en_cours','lot_termine_session_conservee'):
            return resultat  # diagnostic/absence d'action : ne pas boucler à vide
    lab=laboratoire()
    return ('niveau_gagne' if lab.won else 'defaite_sdk' if lab.finished
            else 'auto_lots_termines_session_conservee')


def main(args):
    if args.jeu not in AUTORISES:raise ValueError('Jeu non autorisé')
    demandee=getattr(args, 'graine', None)
    if demandee is not None and not args.neuf:
        raise ValueError('--graine exige --neuf : une reprise conserve sa graine enregistrée')
    args.sortie.mkdir(parents=True,exist_ok=False)
    t=time.monotonic();cpu=time.process_time();cpu_fils=cpu_enfants()
    if args.prefixe:
        a,z,rows=agent_prefixe(args.prefixe);b={'jeu':args.jeu}
    elif args.archives_niveaux:
        from reprise_niveaux_observes import preparer
        a,episodes,b=preparer(args.archives_niveaux)
        if b['jeu']!=args.jeu:raise ValueError('Archives du mauvais jeu')
        z,rows=episodes[0]
    elif args.transfert_depuis:
        ancien,z,rows,b=reconstituer_gagnant(args.transfert_depuis,args.prefixe_gagnant)
        if b['jeu']!=args.jeu:raise ValueError('Trace du mauvais jeu')
        a=agent_transfere(ancien,z['images'][-1],b['actions_disponibles'])
    elif args.neuf:
        a=z=None;rows=[];b={'jeu':args.jeu}
    else:
        if args.source is None:raise ValueError('Source requise pour restauration')
        a,z,rows,b=restaurer_agent(args.source)
        if b['jeu']!=args.jeu:raise ValueError('Trace du mauvais jeu')
    graine=demandee if demandee is not None else b.get('graine_exploration',0)
    meta_graine=metadonnees_graine(graine)
    if a is not None:a.graine_exploration=graine
    hashes=empreintes()
    (args.sortie/'sources.json').write_text(json.dumps(hashes,indent=2))
    lab=LaboP1(args.jeu,1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',
               args.sortie/'N1/partie')
    cout_reacces=sum(len(rs) for _,rs in episodes) if args.archives_niveaux else len(rows)
    appels=0;acces=0;status='restauration';ouverte=True;tentative=1;retries=0;reconciliation_reset=False
    def save():
        parent=time.process_time()-cpu;enfants=cpu_enfants()-cpu_fils
        d={'pid':os.getpid(),'session_ouverte':ouverte,'statut':status,
           'jeu':args.jeu,'niveau':lab.level,'coups_reels':acces+len(lab.rows),'coups_reacces':min(acces+len(lab.rows),cout_reacces),
           'coups_nouveaux':max(0,acces+len(lab.rows)-cout_reacces),'appels_tentes':appels,
           'initialisations':1,'tentative':tentative,'resets_retry':retries,'niveaux_gagnes':lab.rows[-1]['levels_completed'] if lab.rows else lab.completed_baseline,'jeu_gagne':lab.partie_gagnee,
           'secondes':time.monotonic()-t,'cpu_s':parent,
           'cpu_parent_s':parent,'cpu_enfants_recoltes_s':enfants,'cpu_total_recolte_s':parent+enfants,
           'cpu_portee':'process_time parent + RUSAGE_CHILDREN termines/recoltes, hors enfants actifs',
           **meta_graine,
           'modeles_survivants':list(a.chaines) if a else [],'revisions':a.revisions if a else 0,
           'sources_inchangees':empreintes(hashes)==hashes,
           'actions_disponibles':list(lab.actions_disponibles),
           'composition_contextuelle_auto':bool(getattr(a,'composition_contextuelle_auto',False)),
           'recherche_prolongee':bool(getattr(a,'recherche_prolongee',False)),
           'recherche_workers':getattr(a,'recherche_prolongee_workers',2),
           'limite80_desactivee':True,'arret_comparatif_nest_pas_echec_resolution':True}
        tmp=args.sortie/'etat.tmp';tmp.write_text(json.dumps(d,indent=2));tmp.replace(args.sortie/'etat.json')
        (args.sortie/'journal.json').write_text(json.dumps(a.journal if a else [],default=int))
        (lab.output.parent/'journal.json').write_text(json.dumps(a.journal if a else [],default=int))
        return d
    try:
        if args.neuf and not args.transfert_depuis:
            offre_acquisition=list(lab.actions_disponibles)
            for action in [1,2,3,4]*2:
                if lab.finished:break
                if action not in lab.actions_disponibles:continue
                offre_acquisition=list(lab.actions_disponibles)
                appels+=1;lab.play(action,purpose='acquisition_generique')
            nz=np.load(lab.output.with_suffix('.npz'));nr=lab.rows
            a=nouvel_agent(nz['images'],[r['action'] for r in nr],
                [nz[f'film_{i+1}'] for i in range(len(nr))],
                [issue_sdk(r['state'],r['levels_completed'],0) for r in nr],graine_exploration=graine)
            a.offre_avant_action=offre_acquisition
        else:
            assert np.array_equal(lab.image,z['images'][0])
        configurer_composition(a, activation=getattr(args,'composition_contextuelle_auto',None))
        configurer_recherche(a, activation=getattr(args,'recherche_prolongee',None),
            workers=getattr(args,'recherche_workers',None))
        a.journal.append({'type':'configuration_recherche_prolongee','active':a.recherche_prolongee,
            'workers':a.recherche_prolongee_workers})
        a.journal.append({'type':'configuration_composition_contextuelle',
            'active':a.composition_contextuelle_auto,
            'activation_cli':getattr(args,'composition_contextuelle_auto',None) is True})
        a.journal.append({'type':'configuration_graine',**meta_graine})
        for i,row in enumerate(rows):
            if lab.finished:raise ValueError('Épisode terminé pendant réaccès')
            appels+=1
            im,film=lab.play(row['action'],purpose='reacces_rapide_compte')
            if not np.array_equal(im,z['images'][i+1]) or not np.array_equal(film,z[f'film_{i+1}']):
                raise ValueError('Réaccès divergent, état non restauré')
        if args.archives_niveaux:
            for niveau,(zn,rn) in enumerate(episodes[1:],2):
                acces+=len(lab.rows)
                lab=lab.next_level(args.sortie/f'N{niveau}/partie')
                if not np.array_equal(lab.image,zn['images'][0]):raise ValueError('Entrée niveau divergente')
                for i,row in enumerate(rn):
                    if lab.finished:raise ValueError('Fin pendant réaccès multi-niveaux')
                    appels+=1
                    im,film=lab.play(row['action'],purpose='reacces_multiniveau_compte')
                    if not np.array_equal(im,zn['images'][i+1]) or not np.array_equal(film,zn[f'film_{i+1}']):
                        raise ValueError('Réaccès multi-niveaux divergent')
        if args.transfert_depuis:
            acces=len(lab.rows)
            lab=lab.next_level(args.sortie/'N2/partie')
            a=agent_transfere(ancien,lab.image,lab.actions_disponibles)
            configurer_composition(a, activation=getattr(args,'composition_contextuelle_auto',None))
        status='prete_nouvelle_boucle' if args.neuf else 'prete_etat_restaure';print(json.dumps(save()),flush=True)
        def avancer(n):
            nonlocal appels,status
            if reconciliation_reset:raise ValueError("RESET changé de niveau : réconciliation requise")
            for _ in range(n):
                if lab.finished:
                    status='jeu_gagne' if lab.partie_gagnee else 'niveau_gagne' if lab.won else 'defaite_sdk'
                    break
                if empreintes(hashes)!=hashes:raise ValueError('Code changé, session conservée pour diagnostic')
                k=len(lab.rows)+1
                decision_root=(args.sortie if lab.level==1 else args.sortie/f'N{lab.level}') if tentative==1 else lab.output.parent
                folder=decision_root/f'decision_coup_{k:05}';folder.mkdir()
                d=a.decider(lab.actions_disponibles,folder,lab.output,secondes=30)
                (folder/'decision.json').write_text(json.dumps(d,default=int))
                if not d.get('actions'):status=d['statut'];break
                appels+=1;save()
                a.offre_avant_action=list(lab.actions_disponibles)
                im,film=lab.play(d['actions'][0],purpose=d['statut'])
                o=a.observer(d['actions'][0],im,film,
                     issue_sdk(lab.rows[-1]['state'],lab.rows[-1]['levels_completed'],lab.completed_baseline))
                (folder/'observation.json').write_text(json.dumps(o,default=int))
                status='en_cours';save()
            if not lab.finished and status=='en_cours':status='lot_termine_session_conservee'
            if lab.finished:
                status='jeu_gagne' if lab.partie_gagnee else 'niveau_gagne' if lab.won else 'defaite_sdk'
            return status

        def niveau_suivant():
            nonlocal a,lab,acces,status
            if reconciliation_reset:raise ValueError("RESET changé de niveau : réconciliation requise")
            if lab.partie_gagnee or not lab.won:
                raise ValueError('Transfert réservé à un niveau gagné, jeu non terminé')
            nouveau=agent_transfere(a,lab.image,lab.actions_disponibles)
            suivant=lab.next_level(args.sortie/f'N{lab.level+1}/partie')
            acces+=len(lab.rows)
            lab=suivant;a=nouveau;status='niveau_suivant_pret'
            save()

        def retenter():
            nonlocal a,lab,acces,appels,status,tentative,retries,reconciliation_reset
            import copy
            from memoire_episodes import retenir_defaite,separer_episode
            if not lab.finished or lab.won or lab.partie_gagnee:
                raise ValueError('retry exige une défaite observée')
            if empreintes(hashes)!=hashes:
                raise ValueError('Code changé, aucun RESET envoyé')
            # Offre avant le coup fatal : celle transmise au dernier décideur.
            preuves=retenir_defaite(a,getattr(a,'offre_avant_action',lab.actions_disponibles),lab.level)
            ancien=a
            observations=observations_tentatives(ancien)
            ancien.journal.append({'type':'episode_defaite_archive','niveau':lab.level,
                'tentative':tentative,'memoire_negative':preuves,'reset_automatique':False})
            save()
            from avancer_agent_relais import sauver_agent
            snapshot=lab.output.parent/f'agent_avant_retry_{retries+1}.pkl'
            sauver_agent(ancien,snapshot)
            appels+=1;retries+=1
            lab.reset_apres_defaite(purpose='retry_explicite_compte')
            ancien.journal.append({'type':'reset_observe','action':0,'issue':lab.rows[-1]['state'],
                'offre':list(lab.actions_disponibles),'source_episode':str(lab.output)})
            save()
            if lab.finished:
                status='jeu_gagne' if lab.partie_gagnee else 'niveau_gagne' if lab.won else 'defaite_sdk'
                return
            if lab.completed_baseline!=lab.level-1:
                reconciliation_reset=True;status='reset_niveau_inattendu';return
            nouveau=nouvel_agent([lab.image],[],[],[],graine_exploration=graine)
            configurer_composition(nouveau, ancien=ancien)
            configurer_recherche(nouveau, ancien=ancien)
            nouveau.memoire_episodes=preuves
            nouveau.observations_episodes=observations
            nouveau.modeles_episode_precedent=copy.deepcopy({
                **getattr(ancien,'chaines',{}),
                **getattr(ancien,'modeles_physiques_fin_episode',{})})
            nouveau.snapshot_episode_precedent=str(snapshot)
            nouveau.precedents=copy.deepcopy(getattr(ancien,'precedents',[]))
            nouveau.commandes_connues=set(getattr(ancien,'commandes_connues',set())) | {x for x in ancien.actions if isinstance(x,int)}
            # Les anciennes dynamiques restent des candidats archivés, pas un but ni un plan adoptés.
            nouveau.journal=copy.deepcopy(ancien.journal)
            nouveau.journal.append({'type':'nouvelle_tentative','dynamique':'a_revalider',
                'buts_adoptes':False,'memoire_negative':preuves})
            from readmission_episode import installer as readmettre_episode
            readmettre_episode(nouveau,lab.actions_disponibles)
            tentative+=1
            suivant=separer_episode(lab,args.sortie/f'N{lab.level}'/f'tentative_{tentative}'/'partie')
            acces+=len(lab.rows);lab=suivant;a=nouveau;status='nouvelle_tentative_prete'

        for line in sys.stdin:
            try:
                cmd=json.loads(line)
                if cmd['op']=='close':break
                if cmd['op']=='status':print(json.dumps(save()),flush=True);continue
                if cmd['op']=='next_level':
                    niveau_suivant()
                elif cmd['op']=='retry':
                    retenter()
                elif cmd['op']=='advance':
                    n=entier_positif(cmd.get('coups',32),'coups')
                    avancer(n)
                elif cmd['op']=='auto':
                    reprises=cmd.get('reprises',False)
                    if not isinstance(reprises,bool):raise ValueError('reprises doit être booléen')
                    status=piloter_auto(lambda:lab,avancer,niveau_suivant,
                        lots=cmd.get('lots',1),coups=cmd.get('coups',32),
                        retenter=retenter if reprises else None)
                else:raise ValueError('Commande inconnue')
                print(json.dumps(save()),flush=True)
            except Exception as exc:
                status='diagnostic_requis'
                a.journal.append({'type':'erreur_session','message':repr(exc)})
                print(json.dumps(save()),flush=True)
    finally:
        ouverte=False;save()

def arguments_session():
    p=argparse.ArgumentParser()
    p.add_argument('--jeu',required=True);p.add_argument('--source',type=Path)
    p.add_argument('--archives-niveaux',type=Path)
    p.add_argument('--neuf',action='store_true')
    p.add_argument('--composition-contextuelle-auto',action='store_true',default=None,
        help='Activer explicitement la composition contextuelle ; sinon conserver le flag enregistré, défaut inactif')
    p.add_argument('--recherche-prolongee',action='store_true',default=None,
        help='Activer explicitement la recherche prolongée CPU ; défaut inactif au départ neuf, héritage sinon')
    p.add_argument('--recherche-workers',type=int,choices=(1,2),default=None,
        help='Palier prolongé : 1 local poids10, 2 parallèles poids3/10 ; héritage sinon, défaut2')
    p.add_argument('--graine',type=int,default=None,help='Graine exploration P1 (--neuf uniquement, défaut 0), pas une graine SDK')
    p.add_argument('--transfert-depuis',type=Path)
    p.add_argument('--prefixe',type=Path)
    p.add_argument('--prefixe-gagnant',type=Path)
    p.add_argument('--sortie',type=Path,required=True)
    return p

if __name__=='__main__':
    main(arguments_session().parse_args())
