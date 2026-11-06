"""Les capacités héritées proposent une expérience, jamais une vérité du niveau."""
import numpy as np
from objets_identites import occurrences, suivre_motif


def proposer(agent, offre, memo, transport_seul=False):
    from relation_clic_observee import positions, candidats
    from chrysalide.arc3.masque import Masque
    from selection_visuelle_immobile import _vue
    from masque_priorite_contextuelle import cellules_priorite
    cellules=cellules_priorite(agent.images)
    def deja(action):
        return question_deja_observee(agent,action,cellules)
    journal = getattr(agent, 'revalidations_capacites', [])
    attente = getattr(agent, 'revalidation_capacite_attente', None)
    if attente and len(agent.actions) > attente['index']:
        i = attente['index']; motif = np.array(attente['motif'])
        observes = occurrences(agent.images[i+1], motif)
        from referentiel_visible import estimer
        from economie_film_observee import composantes
        palette=attente.get('palette_mobile') or ({int(v) for v in motif.ravel() if v>=0}|{c for c,f,x,y in composantes(agent.images[i]) if f==frozenset(map(tuple,memo['forme']))})
        ref=estimer(agent.images[i],agent.images[i+1],palette)
        dx,dy=ref['translation']
        attendus=set((p[0]+dx,p[1]+dy) for p in attente['supports'])
        exact = (attendus <= set(observes) if attente.get('portee_supports')=='porteurs_seulement' else attendus==set(observes))
        resultat = dict(attente, supports_exacts=exact, referentiel=ref, coup=i+1, but_certifie=False)
        if attente['phase'] == 'mouvement_conjoint':
            ps = positions(agent.images[i+1], frozenset(map(tuple, memo['forme'])))
            resultat['discrimination_valide']=exact
            from mouvement_relatif_film import verifier as verifier_film
            resultat['film_relatif']=verifier_film(agent.images[i],agent.films[i],motif,memo['forme'],attente['associations'])
            resultat['associations'] = [dict(p, conjointe_observee=tuple(p['conjointe']) in ps,
                independante_observee=tuple(p['independante']) in ps) for p in attente['associations']]
        valides=[p for p in resultat.get('film_relatif',{}).get('associations',[]) if p['relation_relative_verifiee']]
        if exact and len(valides)==1:
            import copy
            heritage=next((h for h in getattr(agent,'hypotheses_capacites_heritees',[]) if h.get('episode_source_sha256')==attente['episode_source_sha256']),None)
            if heritage:
                r=copy.deepcopy(heritage['hypothese']);r['decalage']=valides[0]['offset']
                r['association_relative_film']=resultat['film_relatif'];r['coup_preuve']=i+1
                r['validations_prospectives']=[];r['transfert_valide']=False
                r['statut']='association_relative_revalidee_pas_modele_complet'
                agent.memoire_mouvement_conjoint=r
        journal.append(resultat); agent.revalidations_capacites = journal
        agent.revalidation_capacite_attente = None
    from alignement_support_relation import proposer as aligner_support
    d=None if transport_seul else aligner_support(agent,offre,memo)
    if d is not None:return d
    if not transport_seul and getattr(agent,'memoire_mouvement_conjoint',{}).get('association_relative_film'):
        from transport_relationnel import proposer as proposer_transport
        if proposer_transport(agent,offre) is not None:return None
    # Sans route applicable, une capacité active peut encore proposer une expérience
    # dans le nouveau contexte ; son activation n'implique pas une maîtrise globale.
    for heritage in getattr(agent, 'hypotheses_capacites_heritees', []):
        if heritage.get('capacite') != 'mouvement_conjoint':continue
        h=heritage['hypothese']; motif=np.asarray(h['support_motif_stable'])
        supports=occurrences(agent.images[-1],motif)
        if not 2 <= len(supports) <= 6:continue
        try:
            from suivi_partiel_observe import suivre
            series,_=suivre(agent.images,motif,len(supports))
        except ValueError:continue
        from economie_film_observee import composantes
        from referentiel_visible import estimer
        forme=frozenset(map(tuple,memo['forme']))
        palette={int(v) for v in motif.ravel() if v>=0}|{c for c,f,x,y in composantes(agent.images[-1]) if f==forme}
        mouvements={}
        for i,action in enumerate(agent.actions):
            if not isinstance(action,int) or action not in (1,2,3,4):continue
            paire=(series[i],series[i+1])
            if any(v is None for v in paire):
                # Une commande observée avant une entrée dans le champ reste une
                # hypothèse ; aucune identité n'est prolongée à travers ce changement.
                n=len(occurrences(agent.images[i],motif))
                if not 1<=n<=6 or len(occurrences(agent.images[i+1],motif))!=n:continue
                try:paire=([occurrences(g,motif) for g in agent.images[i:i+2]] if n==1 else suivre_motif(agent.images[i:i+2],motif,n))
                except ValueError:continue
            ref=estimer(agent.images[i],agent.images[i+1],palette);rx,ry=ref['translation']
            ds={(q[0]-p[0]-rx,q[1]-p[1]-ry) for p,q in zip(*paire)}
            non_nuls=ds-{(0,0)}
            if len(non_nuls)==1:mouvements.setdefault(action,set()).update(non_nuls)
        mouvements={a:next(iter(ds)) for a,ds in mouvements.items() if len(ds)==1 and a in offre}
        forme=frozenset(map(tuple,memo['forme'])); ps=positions(agent.images[-1],forme)
        offset=h['decalage']; couples=[(p,(p[0]+offset[0],p[1]+offset[1])) for p in supports if (p[0]+offset[0],p[1]+offset[1]) in ps]
        interactions=[] if transport_seul else candidats(ps,memo['regle'])
        # Une relation déjà refusée est une question nouvelle si son support a changé.
        if not couples:
            sur_support=[t for t in interactions if (t[2][0]-offset[0],t[2][1]-offset[1]) in supports]
            if sur_support and 6 in offre:
                s,v,d=min(sur_support); cx=sum(p[0] for p in forme)/len(forme); cy=sum(p[1] for p in forme)/len(forme)
                dx,dy=min(forme,key=lambda p:((p[0]-cx)**2+(p[1]-cy)**2,p))
                action=['clic',s[0]+dx,s[1]+dy]
                if not deja(action):
                    return {'actions':[action],'predictions':[[]],'modeles':[], 'origine':'relation_sur_support_herite_a_tester',
                        'statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu','source':s,'voisin':v,'destination_candidate':d}
        for action,delta in sorted(mouvements.items()):
            futurs=[(p[0]+delta[0],p[1]+delta[1]) for p in supports]
            if any(min(p)<0 or p[0]+motif.shape[1]>agent.images[-1].shape[1] or p[1]+motif.shape[0]>agent.images[-1].shape[0] for p in futurs):continue
            if deja(action):continue # Priorité expérimentale seulement ; graphe intégral inchangé.
            associations=[{'support':list(p),'independante':list(f),'conjointe':[f[0]+delta[0],f[1]+delta[1]]} for p,f in couples]
            if not couples and not any((t[2][0]-offset[0],t[2][1]-offset[1]) in futurs for t in interactions):continue
            phase='mouvement_conjoint' if couples else 'alignement_relation'
            supports_predits=[(p[0]+delta[0],p[1]+delta[1]) for p,f in couples] if couples else futurs
            contrat={'index':len(agent.actions),'phase':phase,'motif':motif.tolist(),'supports':list(map(list,supports_predits)),
                'portee_supports':'porteurs_seulement' if couples else 'hypothese_alignement_tous',
                'autres_supports':'inconnus' if couples else 'hypothese_commune',
                'masque_priorite_heuristique':sorted(map(list,cellules)),
                'associations':associations,'palette_mobile':sorted(palette),'prediction_positions':'avant_recalage_apparent_inconnu','episode_source_sha256':heritage['episode_source_sha256'],
                'garde_navigation':'inconnue_dans_ce_contexte','but_certifie':False}
            agent.revalidation_capacite_attente=contrat
            return {'actions':[action],'predictions':[[]],'modeles':[], 'origine':'revalidation_capacite_heritee',
                'statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu','contrat_hypotheses':contrat,
                'activation_transport':False,'abstentions':['but','garde','autres_objets','images_intermediaires']}
    return None


def question_deja_observee(agent, action, cellules):
    """Priorité expérimentale : conserver le contexte du masque au moment de la question.

    Ce rapprochement ne modifie ni les états ni le graphe, et ne prouve pas
    l'équivalence causale lorsque le compteur masque une phase pertinente.
    """
    from selection_visuelle_immobile import _vue
    masques={}
    for preuve in getattr(agent,'revalidations_capacites',[]):
        i=preuve.get('index')
        if isinstance(i,int):
            masques.setdefault(i,set()).update(map(tuple,preuve.get('masque_priorite_heuristique',[])))
    for i,(a,g) in enumerate(zip(agent.actions,agent.images)):
        if a != action:continue
        for masque in (cellules,masques.get(i,set())):
            if np.array_equal(_vue(g,masque),_vue(agent.images[-1],masque)):
                return True
    return False
