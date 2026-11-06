"""Transport provisoire vers une nouvelle interaction de la relation déjà apprise."""
from collections import deque
import numpy as np
from objets_variables import localiser
from garde_support_navigation import apprendre


def proposer(agent,offre,explorer_gardes=False):
    from relation_clic_observee import positions,candidats
    r=getattr(agent,'memoire_mouvement_conjoint',None);memo=getattr(agent,'memoire_relation_clic',None)
    if not r or not memo or r.get('refutee') or r.get('a_revoir_perception') or r.get('navigation_a_revoir'):return None
    stable=np.asarray(r['support_motif_stable']);forme=frozenset(map(tuple,r['forme']))
    def situer(image):
        if not r.get('association_relative_film'):return localiser(image,stable)
        from objets_identites import occurrences
        ps=positions(image,forme);off=r['decalage']
        cs=[p for p in occurrences(image,stable) if (p[0]+off[0],p[1]+off[1]) in ps]
        if len(cs)!=1:raise ValueError('Rôle porté ambigu')
        return cs[0]
    attente=getattr(agent,'transport_en_attente',None)
    if attente and len(agent.actions)>attente['index']:
        i=attente['index']
        if agent.issues[i]=='continue':
            try:pos=situer(agent.images[i+1])
            except ValueError:r['a_revoir_perception']=True;return None
            cible=list(attente['support']);fc=list(attente['forme'])
            if r.get('association_relative_film'):
                from referentiel_visible import estimer
                palette={int(v) for v in stable.ravel() if v>=0}
                from economie_film_observee import composantes
                palette|={c for c,f,x,y in composantes(agent.images[i]) if f==forme}
                ref=estimer(agent.images[i],agent.images[i+1],palette)
                cible=[v+d for v,d in zip(cible,ref['translation'])];fc=[v+d for v,d in zip(fc,ref['translation'])]
            exact=list(pos)==cible and tuple(fc) in positions(agent.images[i+1],forme)
            r.setdefault('validations_prospectives',[]).append({'coup':i+1,'exact':exact,'action':agent.actions[i]})
            if list(pos)!=cible:
                r['navigation_a_revoir']=True;return None
            if not exact:r['refutee']=True;return None
        agent.transport_en_attente=None
    try:depart=situer(agent.images[-1])
    except ValueError:return None
    offset=r['decalage'];porte=(depart[0]+offset[0],depart[1]+offset[1]);ps=positions(agent.images[-1],forme)
    if porte not in ps:return None
    complet=np.asarray(r.get('support_motif_complet',r['support_motif_stable']))
    if r.get('association_relative_film'):
        from objets_identites import occurrences,suivre_motif
        from referentiel_visible import estimer
        from economie_film_observee import composantes
        try:
            from suivi_partiel_observe import suivre
            series,_=suivre(agent.images,stable,len(occurrences(agent.images[-1],stable)))
        except ValueError:return None
        piste=series[-1].index(depart);hist=[s[piste] if s is not None else None for s in series]
        palette={int(v) for v in stable.ravel() if v>=0}|{c for c,f,x,y in composantes(agent.images[-1]) if f==forme}
        shifts=[estimer(a,b,palette)['translation'] for a,b in zip(agent.images,agent.images[1:])]
        gardes,mouvements,hist=apprendre(agent.images,agent.actions,complet,hist,shifts)
    else:gardes,mouvements,hist=apprendre(agent.images,agent.actions,complet)
    if not gardes:return None
    decor=np.asarray(agent.images[-1]).copy()
    # Réutiliser seulement pixels antérieurement observés hors support, jamais inventer le sol.
    for oy,ox in np.argwhere(complet>=0):
        gx,gy=depart[0]+ox,depart[1]+oy;decor[gy,gx]=-1
        for image,p in reversed(list(zip(agent.images[:-1],hist[:-1]))):
            if p is None:continue
            xx,yy=gx-p[0],gy-p[1]
            if not(0<=yy<complet.shape[0] and 0<=xx<complet.shape[1] and complet[yy,xx]>=0):decor[gy,gx]=image[gy,gx];break
    autres=ps-{porte};file=deque([(depart,[])]);vus={depart};frontieres=[]
    while file and len(vus)<=decor.size:
        pos,route=file.popleft();mobile=(pos[0]+offset[0],pos[1]+offset[1])
        interactions=[t for t in candidats(autres|{mobile},memo['regle']) if mobile in t[:2] and any(v in autres for v in t[:2])]
        if interactions:
            if route:
                code=route[0];d=mouvements[code];suite=[depart[j]+d[j] for j in (0,1)];fp=[suite[j]+offset[j] for j in (0,1)]
                agent.transport_en_attente={'index':len(agent.actions),'support':suite,'forme':fp}
                return {'actions':[code],'predictions':[[]],'modeles':[],
                  'origine':'transport_vers_relation','statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu',
                  'route_acces_hypothetique':route,'support_cible':list(pos),
                  'garde_navigation':'desaccord_entre_gardes_candidates_experience_un_pas' if explorer_gardes else 'accord_gardes_provisoires',
                  'votes_premier_pas':[sum(int(decor[suite[1]+g['offset'][1],suite[0]+g['offset'][0]]) in g['permis'] for g in gardes),len(gardes)],
                  'contrat_prediction_partielle':{'action':code,'objets':{'motif':stable.tolist()},'position_candidate':suite,
                    'forme_candidate':fp,'statut':'transport_provisoire_a_verifier','but_certifie':False,
                    'abstentions':['but','autres_objets','images_intermediaires']}}
            if 6 not in offre:return None
            # Même priorité empirique que le proposeur relationnel : un refus ne réfute pas la loi.
            echecs=memo.get('sondes_selection_non_confirmees',[])
            def priorite(t):
                return (sum(e['positions']==sorted(map(list,ps)) and e['sources']==[list(t[0]),list(t[1])] and e['destination']==list(t[2]) for e in echecs),t)
            s,v,d=min(interactions,key=priorite);cx=sum(x for x,y in forme)/len(forme);cy=sum(y for x,y in forme)/len(forme)
            dx,dy=min(forme,key=lambda p:(p[0]-cx)**2+(p[1]-cy)**2)
            return {'actions':[['clic',s[0]+dx,s[1]+dy]],'predictions':[[]],'modeles':[],
              'origine':'selection_apres_transport','statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu',
              'source':s,'voisin':v,'destination_candidate':d}
        for code,d in sorted(mouvements.items()):
            if code not in offre:continue
            p=(pos[0]+d[0],pos[1]+d[1])
            if p in vus or min(p)<0 or p[0]+complet.shape[1]>decor.shape[1] or p[1]+complet.shape[0]>decor.shape[0]:continue
            votes=[int(decor[p[1]+g['offset'][1],p[0]+g['offset'][0]]) in g['permis'] for g in gardes]
            if not all(votes) and not (explorer_gardes and any(votes)):
                mobile_p=(p[0]+offset[0],p[1]+offset[1])
                if any(votes) and any(mobile_p in t[:2] and any(v in autres for v in t[:2]) for t in candidats(autres|{mobile_p},memo['regle'])):
                    frontieres.append((route+[code],sum(votes),len(votes)))
                continue
            vus.add(p);file.append((p,route+[code]))
    if frontieres:
        route,oui,total=min(frontieres,key=lambda v:(len(v[0]),-v[1],v[0]))
        code=route[0];d=mouvements[code];suite=[depart[j]+d[j] for j in (0,1)];fp=[suite[j]+offset[j] for j in (0,1)]
        agent.transport_en_attente={'index':len(agent.actions),'support':suite,'forme':fp}
        return {'actions':[code],'predictions':[[]],'modeles':[], 'origine':'transport_vers_frontiere_relation',
            'statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu',
            'route_hypothetique':route,'question':'Les gardes en désaccord permettent-elles la prochaine interaction ?',
            'votes_frontiere':[oui,total],'contrat_prediction_partielle':{'action':code,'objets':{'motif':stable.tolist()},
                'position_candidate':suite,'forme_candidate':fp,'but_certifie':False,
                'statut':'prediction_relative_avant_recalage_provisoire','abstentions':['but','autres_objets','images_intermediaires','garde_frontiere']}}
    if not explorer_gardes:
        return proposer(agent,offre,explorer_gardes=True)
    return None
