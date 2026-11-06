"""Réutiliser le BFS de gardes pour rendre une relation géométrique expérimentable."""
import numpy as np
from objets_identites import occurrences
from suivi_partiel_observe import suivre
from referentiel_visible import estimer
from garde_support_navigation import proposer as naviguer


def proposer(agent,offre,memo):
    from relation_clic_observee import positions,candidats
    h=getattr(agent,'memoire_mouvement_conjoint',None)
    if h is None:
        hs=[x['hypothese'] for x in getattr(agent,'hypotheses_capacites_heritees',[]) if x.get('capacite')=='mouvement_conjoint']
        if len(hs)!=1:return None
        h=hs[0]
    stable=np.asarray(h['support_motif_stable']);full=np.asarray(h['support_motif_complet'])
    forme=frozenset(map(tuple,memo['forme']));ps=positions(agent.images[-1],forme)
    supports=occurrences(agent.images[-1],stable);off=h['decalage']
    if any((p[0]+off[0],p[1]+off[1]) in ps for p in supports):return None
    if not 2<=len(supports)<=6:return None
    try:series,diag=suivre(agent.images,stable,len(supports))
    except ValueError:return None
    from economie_film_observee import composantes
    palette={int(v) for v in stable.ravel() if v>=0}|{c for c,f,x,y in composantes(agent.images[-1]) if f==forme}
    refs=[estimer(a,b,palette)['translation'] for a,b in zip(agent.images,agent.images[1:])]
    attente=getattr(agent,'alignement_support_attente',None)
    if attente and len(agent.actions)>attente['index']:
        i=attente['index'];observe=series[i+1]
        attendu=tuple(v+d for v,d in zip(attente['position_candidate'],refs[i]))
        exact=observe is not None and observe[attente['piste']]==attendu
        agent.__dict__.setdefault('validations_alignement_support',[]).append({'coup':i+1,'exact':exact,'piste':attente['piste'],'recalage_provisoire':refs[i]})
        agent.alignement_support_attente=None
    cibles={(d[0]-off[0],d[1]-off[1]) for s,v,d in candidats(ps,memo['regle'])}
    # Expérience de remise en relation : rejoindre une forme visible ne certifie
    # pas sa prise en charge ; le mouvement conjoint devra encore être observé.
    cibles|={(p[0]-off[0],p[1]-off[1]) for p in ps}
    if not cibles:return None
    choix=[]
    for piste in range(len(supports)):
        hist=[s[piste] if s else None for s in series]
        d=naviguer(agent.images,agent.actions,full,offre,positions_connues=hist,recalages=refs,cibles=cibles)
        if d:choix.append((len(d['route_acces_hypothetique']),piste,d))
    if not choix:return None
    _,piste,d=min(choix,key=lambda q:(q[0],q[1]))
    d['origine']='alignement_support_vers_relation';d['suivi']=diag
    d['associations_candidates']=[{'piste':p,'route':v['route_acces_hypothetique']} for _,p,v in choix]
    d['contrat_prediction_partielle']['objets']['motif']=stable.tolist()
    d['contrat_prediction_partielle']['piste']=piste
    d['contrat_prediction_partielle']['abstentions']+=['autres_supports','recalage_futur']
    agent.alignement_support_attente={'index':len(agent.actions),'piste':piste,'position_candidate':d['contrat_prediction_partielle']['position_candidate']}
    return d
