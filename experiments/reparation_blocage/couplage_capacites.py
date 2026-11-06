"""Expérience de composition : changer une occupation avant de retester un effet."""
from collections import deque
import numpy as np
from objets_variables import ObjetsVariables,localiser
from garde_support_navigation import apprendre


def route_relation(ps,regle,cible,essais_non_confirmes=()):
    from relation_clic_observee import candidats
    file=deque([(frozenset(ps),[])]);vus={frozenset(ps)}
    while file:
        etat,route=file.popleft()
        if cible not in etat:return route
        for s,v,d in candidats(set(etat),regle):
            if any(e['positions']==sorted(map(list,etat)) and e['sources']==[list(s),list(v)] and e['destination']==list(d) for e in essais_non_confirmes):continue
            suite=frozenset((set(etat)-{s,v})|{d})
            if suite not in vus:vus.add(suite);file.append((suite,route+[(s,v,d)]))
    return None


def proposer(agent,offre,memo):
    from relation_clic_observee import positions
    forme=frozenset(map(tuple,memo['forme']));ps=positions(agent.images[-1],forme)
    objectif=getattr(agent,'experience_couplage',None)
    if objectif and objectif.get('index_sonde_finale') is not None:
        if len(agent.actions)>objectif['index_sonde_finale']:
            if 'index_sonde_conjointe' not in objectif:
                from sonde_mouvement_conjoint import proposer as proposer_conjoint
                d=proposer_conjoint(agent,offre,objectif,memo)
                if d is not None:
                    objectif['index_sonde_conjointe']=len(agent.actions)
                    return d
            from sonde_mouvement_conjoint import memoriser
            memoriser(agent,objectif,memo)
            agent.experience_couplage=None
        return None
    # Même extracteur contigu que l'arbitre ; aucune identité de jeu.
    segments=[];debut=None
    for i,a in enumerate(agent.actions+[None]):
        if isinstance(a,int) and a in (1,2,3,4):
            if debut is None:debut=i
        elif debut is not None:segments.append((debut,i));debut=None
    if not segments:return None
    debut,fin=max(segments,key=lambda x:x[1]-x[0])
    try:vue=ObjetsVariables(agent.images[debut:fin+1],agent.actions[debut:fin])
    except (ValueError,TypeError):return None
    motifs=list(vue.mobiles)
    if objectif and 'motif_mobile' in objectif:
        motifs=[np.asarray(objectif['motif_mobile'])]
    elif objectif:
        # Compatibilité des expériences anciennes : retrouver l'ancre déclarée.
        for d,f in segments:
            try:autres=ObjetsVariables(agent.images[d:f+1],agent.actions[d:f]).mobiles
            except (ValueError,TypeError):continue
            for m in autres:
                try:coherent=list(localiser(agent.images[objectif.get('index_baseline',len(agent.images)-1)],m))==objectif['position_mobile']
                except ValueError:continue
                if coherent:motifs=[m];objectif['motif_mobile']=m.tolist();break
            if 'motif_mobile' in objectif:break
    choix=[]
    for motif in motifs:
        try:pos=localiser(agent.images[-1],motif)
        except ValueError:
            from ancre_sous_attribut import retrouver
            preuve=retrouver(agent.images[-1],motif,objectif['position_mobile'],getattr(agent,'dernier_contrat_relation',None)) if objectif else None
            if preuve is None:continue
            pos=tuple(preuve['position']);objectif['ancre_partielle']=preuve
        if objectif and list(pos)==objectif['position_mobile']:
            code=objectif['commande'];cible=tuple(objectif['forme_cible'])
            if code not in offre:return None
            if cible not in ps:
                objectif['index_sonde_finale']=len(agent.actions)
                return {'actions':[code],'predictions':[[]],'modeles':[],
                        'origine':'comparaison_navigation_apres_relation','statut':'experience_conditionnelle',
                        'but':'inconnu','risque':'inconnu','hypotheses':['garde_depends_occupation','garde_independante_occupation'],
                        'objectif_experience':objectif}
        gardes,mouvements,_=apprendre(agent.images,agent.actions,motif)
        for code,delta in mouvements.items():
            if code not in offre:continue
            dest=(pos[0]+delta[0],pos[1]+delta[1]);pixels={(dest[0]+g['offset'][0],dest[1]+g['offset'][1]) for g in gardes}
            if not pixels:continue
            for cible in ps:
                occupes={(cible[0]+x,cible[1]+y) for x,y in forme}
                if not pixels<=occupes:continue
                essais=[]
                if objectif and objectif.get('position_mobile')==list(pos) and 'index_baseline' in objectif:
                    essais=[e for e in memo.get('sondes_selection_non_confirmees',[]) if e['coup']>objectif['index_baseline']]
                route=route_relation(ps,memo['regle'],cible,essais)
                if route:choix.append((len(route),code,cible,route,pos,motif.tolist()))
    if not choix:return None
    _,code,cible,route,pos,motif_mobile=min(choix)
    objectif={'commande':code,'forme_cible':list(cible),'position_mobile':list(pos),
              'route_hypothetique':[[list(x) for x in t] for t in route],'motif_mobile':motif_mobile,'but':'inconnu'}
    precedent=getattr(agent,'experience_couplage',None)
    if precedent and all(precedent.get(k)==objectif[k] for k in ('commande','forme_cible','position_mobile')):
        objectif.update({k:v for k,v in precedent.items() if k=='index_baseline'})
    agent.experience_couplage=objectif
    # Baseline de la même action au même état observable ; compteur seul ignoré.
    def meme(g):
        a=np.asarray(g).copy();b=np.asarray(agent.images[-1]).copy()
        for y,x in vue.hud:a[y,x]=b[y,x]=-1
        return np.array_equal(a,b)
    if 'index_baseline' not in objectif and not any(a==code and meme(g) for a,g in zip(agent.actions,agent.images)):
        objectif['index_baseline']=len(agent.actions)
        return {'actions':[code],'predictions':[[]],'modeles':[],
                'origine':'baseline_couplage_navigation','statut':'experience_conditionnelle',
                'but':'inconnu','risque':'inconnu','objectif_experience':objectif}
    s,v,d=route[0];mx=sum(x for x,y in forme)/len(forme);my=sum(y for x,y in forme)/len(forme)
    ox,oy=min(forme,key=lambda p:(p[0]-mx)**2+(p[1]-my)**2)
    return {'actions':[['clic',s[0]+ox,s[1]+oy]],'predictions':[[]],'modeles':[],
            'origine':'intervention_relation_pour_couplage','statut':'experience_conditionnelle',
            'but':'inconnu','risque':'inconnu','source':s,'voisin':v,'destination_candidate':d,
            'objectif_experience':objectif}
