"""Prototype de relation affine apprise ; aucun but, identité de jeu ou action SDK."""
from math import gcd
from economie_film_observee import composantes
from agent_p1.generique import objets


def positions(image,forme):
    return {(x,y) for c,f,x,y in composantes(image) if f==forme}


def apprendre(exemples,forme):
    preuves=[]
    for avant,apres,selection in exemples:
        b=positions(avant,forme);a=positions(apres,forme);enleves=b-a;ajoutes=a-b
        if len(enleves)!=2 or len(ajoutes)!=1:continue
        source=min(enleves,key=lambda p:(p[0]-selection[1])**2+(p[1]-selection[2])**2)
        voisin=next(iter(enleves-{source}));destination=next(iter(ajoutes))
        v=(voisin[0]-source[0],voisin[1]-source[1]);d=(destination[0]-source[0],destination[1]-source[1])
        rapports={d[i]/v[i] for i in range(2) if v[i]}
        if len(rapports)!=1 or any(d[i] for i in range(2) if not v[i]):continue
        ratio=rapports.pop()
        if not float(ratio).is_integer():continue
        preuves.append({'source':source,'voisin':voisin,'destination':destination,'ratio':int(ratio),'vecteur':v})
    ratios={p['ratio'] for p in preuves}
    if len(ratios)!=1:raise ValueError('Relation affine absente ou ambiguë')
    return {'ratio':ratios.pop(),'preuves':preuves,'but':'inconnu','portee':'hypothese_relationnelle_provisoire',
            'rotation_transfert':'hypothese_non_validee','consommation':'non_prouvee'}


def candidats(ps,regle):
    # Transfert rotation/réflexion proposé seulement ; ne constitue pas une preuve de légalité.
    longueurs={abs(p['vecteur'][0])+abs(p['vecteur'][1]) for p in regle['preuves']}
    out=[]
    for s in sorted(ps):
        for v in sorted(ps-{s}):
            dx,dy=v[0]-s[0],v[1]-s[1]
            if dx and dy:continue
            if abs(dx)+abs(dy) not in longueurs:continue
            d=(s[0]+regle['ratio']*dx,s[1]+regle['ratio']*dy)
            if d in ps or min(d)<0 or max(d)>=64:continue
            out.append((s,v,d))
    return out


def proposer(image,forme,regle,essais_non_confirmes=()):
    ps=positions(image,forme);choix=[]
    for s,v,d in candidats(ps,regle):
        futur=(ps-{s,v})|{d}
        echecs=sum(e['positions']==sorted(map(list,ps)) and e['sources']==[list(s),list(v)] and e['destination']==list(d) for e in essais_non_confirmes)
        choix.append((len(candidats(futur,regle)),s,v,d,echecs))
    if not choix:return None
    score,s,v,d,echecs=max(choix,key=lambda q:(-q[4],q[0],-q[1][1],-q[1][0]))
    if echecs:return None # proposer autre découverte ; ce n'est pas une interdiction physique
    # Pixel de la forme existante le plus proche du centre (jamais un trou).
    fx=sum(x for x,y in forme)/len(forme);fy=sum(y for x,y in forme)/len(forme)
    dx,dy=min(forme,key=lambda p:((p[0]-fx)**2+(p[1]-fy)**2,p[1],p[0]))
    return {'actions':[['clic',s[0]+dx,s[1]+dy]],'predictions':[[]],'modeles':[],
        'statut':'experience_conditionnelle','origine':'relation_observee_et_continuation',
        'but':'inconnu','risque':'inconnu','source':s,'voisin':v,'destination_candidate':d,
        'actions_futures_hypothetiques':score,'regle':regle,
        'condition':'Observer les marqueurs avant toute action vers destination ; pas plan certifié'}


def actualiser(agent):
    """Mémoire partielle : exemples observés, jamais but hérité par simple corrélation."""
    import copy
    from selection_visuelle_immobile import analyser
    memo=copy.deepcopy(getattr(agent,'memoire_relation_clic',None))
    attente=getattr(agent,'relation_clic_en_attente',None)
    if attente and len(agent.actions)>attente['index']:
        i=attente['index'];forme=frozenset(map(tuple,attente['forme']))
        if agent.actions[i]==attente['action'] and agent.issues[i]=='continue':
            ps=positions(agent.images[i],forme)
            attendu=(ps-set(map(tuple,attente['sources'])))|{tuple(attente['destination'])}
            from contrat_prediction_partielle import contrat_relation, verifier
            diagnostic=verifier(contrat_relation(attente),agent.images[i],agent.actions[i],agent.images[i+1],agent.issues[i])
            agent.diagnostic_prediction_partielle=diagnostic
            if diagnostic['exact'] is True:agent.dernier_contrat_relation=contrat_relation(attente)
            exact=diagnostic['exact']
            if exact is None:
                agent.relation_clic_en_attente=None
                return memo
            if memo:
                memo.setdefault('validations_prospectives',[]).append({'coup':i+1,'exact':exact})
                if not exact:memo['refutee']=True
        agent.relation_clic_en_attente=None
    if memo and memo.get('refutee'):
        from diagnostic_champ_commun import reexaminer
        reexaminer(agent,memo)
        agent.memoire_relation_clic=memo
        return memo
    exemples=[];forme=None;preuves=[]
    for h in analyser(agent.images,agent.actions,agent.films,agent.issues):
        i=h['coup_activation']
        if i>=len(agent.actions) or agent.issues[i]!='continue':continue
        action=agent.actions[i]
        if not isinstance(action,(list,tuple)) or not any(abs(action[1]-o['x'])<=1 and abs(action[2]-o['y'])<=1 for o in h['marqueurs_distants']):continue
        formes={f for c,f,x,y in composantes(agent.images[i]) if c==h['ancre']['c'] and len(f)==h['ancre']['n']}
        if len(formes)!=1:continue
        f=formes.pop()
        if forme is not None and f!=forme:continue
        try:r=apprendre([(agent.images[i],agent.images[i+1],h['action_activation'])],f)
        except ValueError:continue
        forme=f;exemples.append((agent.images[i],agent.images[i+1],h['action_activation']));preuves.append(i+1)
    if exemples:
        try:regle=apprendre(exemples,forme)
        except ValueError:return memo
        if memo and (memo['regle']['ratio']!=regle['ratio'] or frozenset(map(tuple,memo['forme']))!=forme):
            memo['refutee']=True
        else:
            memo={**(memo or {}),'forme':sorted(map(list,forme)),'regle':regle,
                'coups_preuves':preuves,'refutee':False,'but_certifie':False,
                'portee':'hypothese_partielle_de_dynamique','transfert_confirme':False}
    if memo:agent.memoire_relation_clic=memo
    return memo


def proposer_agent(agent,offre):
    import numpy as np
    from selection_visuelle_immobile import analyser,_vue
    if 6 not in offre:return None
    memo=actualiser(agent)
    if not memo:return None
    if memo.get('refutee'):
        # La réfutation d'une relation de clic ne réfute pas un transport hérité.
        from revalidation_capacites_heritees import proposer as revalider
        return revalider(agent,offre,memo,transport_seul=True)
    from passage_clic_observe import actualiser as actualiser_passages
    actualiser_passages(agent,memo)
    forme=frozenset(map(tuple,memo['forme']))
    if getattr(agent,'selection_heritee_en_attente',None):
        from selection_heritee_sans_cible import proposer as explorer_selection
        d=explorer_selection(agent,offre,memo)
        if d is not None:return d
    # Une destination ne devient action qu'après confirmation visuelle indépendante.
    demande=getattr(agent,'relation_clic_selection',None)
    if demande and len(agent.actions)>demande['index']:
        i=demande['index'];agent.relation_clic_selection=None
        if len(agent.actions)==i+1 and agent.actions[i]==demande['action']:
            hs=analyser(agent.images,agent.actions,agent.films,agent.issues)
            h=next((h for h in reversed(hs) if h['coup_activation']==len(agent.actions)),None)
            if h:
                x,y=demande['destination'];w=max(x for x,y in forme)+1;ht=max(y for x,y in forme)+1
                cs=[o for o in h['marqueurs_distants'] if x-1<=o['x']<=x+w and y-1<=o['y']<=y+ht]
                if not cs:
                    from marqueur_superpose import candidat as marqueur_superpose
                    surimpression=marqueur_superpose(agent.images[i],agent.images[i+1],demande['destination'],forme)
                    if surimpression is not None:cs=[surimpression]
                if cs:
                    c=cs[0];action=['clic',c['x'],c['y']]
                    agent.relation_clic_en_attente={'index':len(agent.actions),'action':action,
                        'sources':demande['sources'],'destination':demande['destination'],'forme':memo['forme']}
                    from contrat_prediction_partielle import contrat_relation
                    contrat=contrat_relation(agent.relation_clic_en_attente)
                    return {'contrat_prediction_partielle':contrat,'actions':[action],'predictions':[[]],'modeles':[],'statut':'experience_conditionnelle',
                        'origine':'relation_clic_marqueur_confirme','but':'inconnu','risque':'inconnu',
                        'prediction_partielle':agent.relation_clic_en_attente,'marqueurs_observes':cs}
            memo.setdefault('sondes_selection_non_confirmees',[]).append({
                'positions':sorted(map(list,positions(agent.images[i],forme))),
                'sources':[list(v) for v in demande['sources']],
                'destination':list(demande['destination']),
                'coup':i+1,'portee':'priorite_experimentale_pas_preuve_impossibilite'})
    from couplage_capacites import proposer as proposer_couplage
    objectif=getattr(agent,'experience_couplage',None)
    if objectif and objectif.get('index_sonde_conjointe') is not None and len(agent.actions)>objectif['index_sonde_conjointe']:
        from sonde_mouvement_conjoint import memoriser
        memoriser(agent,objectif,memo)
        agent.experience_couplage=None
    from transport_relationnel import proposer as proposer_transport
    d=proposer_transport(agent,offre)
    if d is None:
        from revalidation_capacites_heritees import proposer as revalider_heritage
        d=revalider_heritage(agent,offre,memo)
        if d is None:d=proposer_transport(agent,offre)
    if d is None:d=proposer_couplage(agent,offre,memo)
    if d is not None and 'source' not in d:return d
    if d is None:
        from arbitre_capacites_partielles import proposer_navigation
        navigation=proposer_navigation(agent,offre)
        if navigation is not None:
            if navigation.get('preuve',{}).get('repetitions_position_action',0)>0:
                from selection_heritee_sans_cible import proposer as explorer_selection
                alternative=explorer_selection(agent,offre,memo)
                if alternative is not None:
                    alternative['priorite']='changer_capacite_avant_repetition_navigation'
                    return alternative
            return navigation
        d=proposer(agent.images[-1],forme,memo['regle'],memo.get('sondes_selection_non_confirmees',[]))
    if d is None:
        from selection_heritee_sans_cible import proposer as explorer_selection
        return explorer_selection(agent,offre,memo)
    # Ne pas reboucler sur une sélection déjà testée dans le même contexte perceptif.
    from chrysalide.arc3.masque import Masque
    m=Masque()
    for a,b in zip(agent.images,agent.images[1:]):m.observer(np.asarray(a).tolist(),np.asarray(b).tolist())
    cellules=m.cellules();cur=_vue(agent.images[-1],cellules)
    if any(a==d['actions'][0] and np.array_equal(_vue(g,cellules),cur) for g,a in zip(agent.images,agent.actions)):return None
    agent.relation_clic_selection={'index':len(agent.actions),'action':d['actions'][0],
        'sources':[d['source'],d['voisin']],'destination':d['destination_candidate']}
    if d.get('origine') not in ('intervention_relation_pour_couplage','selection_apres_transport'):d['origine']='relation_clic_observee'
    d['memoire_provisoire']=True
    return d


def memoire_transferee(ancien,image):
    import copy
    memo=actualiser(copy.deepcopy(ancien))
    if not memo or memo.get('refutee') or len(memo['coups_preuves'])<2:raise ValueError('Relation partielle insuffisante')
    forme=frozenset(map(tuple,memo['forme']))
    if len(positions(image,forme))<2:raise ValueError('Forme source non réaffectable')
    m=copy.deepcopy(memo);m.pop('sondes_selection_non_confirmees',None);m['transfert_confirme']=False;m['preuves_niveau_precedent']=m.pop('coups_preuves');m['coups_preuves']=[]
    m['validation_requise']='marqueurs locaux puis prédiction prospective ; aucun but certifié'
    return m
