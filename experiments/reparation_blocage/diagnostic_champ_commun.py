"""Une contradiction écran peut laisser une règle locale encore admissible."""
import numpy as np


def comparer(attendu, observe, forme, dimensions, translation):
    h,w=dimensions;dx,dy=translation
    fw=max(x for x,y in forme)+1;fh=max(y for x,y in forme)+1
    def commun(p):
        x,y=p
        return 0<=x and x+fw<=w and 0<=y and y+fh<=h and 0<=x-dx and x-dx+fw<=w and 0<=y-dy and y-dy+fh<=h
    projetes={(x+dx,y+dy) for x,y in attendu}
    if not projetes or not all(commun(p) for p in projetes):return None
    vus=set(map(tuple,observe));locaux={p for p in vus if commun(p)}
    return {'compatible':projetes==locaux,'attendu_local':sorted(map(list,projetes)),
            'observe_local':sorted(map(list,locaux)),'hors_champ_precedent':sorted(map(list,vus-locaux)),
            'population_totale_verifiee':False,'but_certifie':False}


def reexaminer(agent,memo):
    from economie_film_observee import composantes
    from referentiel_visible import estimer
    d=getattr(agent,'diagnostic_prediction_partielle',{})
    echecs=[v['coup'] for v in memo.get('validations_prospectives',[]) if v.get('exact') is False]
    if not echecs or not d.get('attendu') or not d.get('observe'):return False
    k=echecs[-1]
    if any(v['coup']==k for v in getattr(agent,'diagnostics_champ_commun',[])):return False
    if not 0<k<=len(agent.actions) or agent.issues[k-1]!='continue':return False
    forme=frozenset(map(tuple,memo['forme']));avant=agent.images[k-1];apres=agent.images[k]
    palette={c for c,f,x,y in composantes(avant) if f==forme}
    for heritage in getattr(agent,'hypotheses_capacites_heritees',[]):
        motif=heritage.get('hypothese',{}).get('support_motif_stable',[])
        palette.update(int(c) for ligne in motif for c in ligne if c>=0)
    ref=estimer(avant,apres,palette)
    if not ref['retenu'] or ref['translation']==[0,0]:return False
    r=comparer(d['attendu'],d['observe'],forme,np.asarray(apres).shape,ref['translation'])
    if r is None:return False
    agent.__dict__.setdefault('diagnostics_champ_commun',[]).append({'coup':k,'diagnostic_ecran':dict(d),'referentiel':ref,**r})
    if not r['compatible']:return False
    memo['refutee']=False
    memo['portee']='hypothese_locale_conditionnelle_au_recalage'
    memo['population_totale_verifiee']=False
    memo['reouverture_champ_commun']={'coup':k,'referentiel':ref,'preuve':'compatibilite_locale_non_certification_globale'}
    return True
