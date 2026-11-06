"""Gardes de support provisoires à partir d'un motif suivi, sans but fourni."""
from collections import deque
import numpy as np
from objets_variables import localiser


def apprendre(images,actions,motif,positions_connues=None,recalages=None):
    positions=[]
    for g in images:
        try:positions.append(localiser(g,motif))
        except ValueError:positions.append(None)
    if positions_connues is not None:positions=list(positions_connues)
    recalages=recalages or [(0,0)]*len(actions)
    deltas={}
    for k,a in enumerate(actions):
        if not isinstance(a,int) or a not in (1,2,3,4) or positions[k] is None or positions[k+1] is None:continue
        d=tuple(b-c-r for b,c,r in zip(positions[k+1],positions[k],recalages[k]))
        if d!=(0,0):deltas.setdefault(a,set()).add(d)
    mouvements={a:next(iter(ds)) for a,ds in deltas.items() if len(ds)==1}
    exemples=[]
    for k,a in enumerate(actions):
        if not isinstance(a,int) or a not in mouvements or positions[k] is None or positions[k+1] is None:continue
        cible=tuple(p+d for p,d in zip(positions[k],mouvements[a]))
        if min(cible)<0 or cible[0]+motif.shape[1]>images[k].shape[1] or cible[1]+motif.shape[0]>images[k].shape[0]:continue
        exemples.append((k,cible,positions[k+1]==tuple(c+r for c,r in zip(cible,recalages[k]))))
    gardes=[]
    for oy,ox in np.argwhere(motif>=0):
        permis={int(images[k][p[1]+oy,p[0]+ox]) for k,p,ok in exemples if ok}
        bloques={int(images[k][p[1]+oy,p[0]+ox]) for k,p,ok in exemples if not ok}
        if permis and bloques and not permis&bloques:
            gardes.append({'offset':[int(ox),int(oy)],'permis':sorted(permis),'bloques_observes':sorted(bloques)})
    return gardes,mouvements,positions


def proposer(images,actions,motif,offre,positions_connues=None,recalages=None,cibles=None,explorer_inconnus=False):
    images=list(map(np.asarray,images));gardes,mouvements,positions=apprendre(images,actions,motif,positions_connues,recalages)
    if not gardes or positions[-1] is None:return None
    # Les pixels sous le mobile sont inconnus, sauf s'ils ont été réellement vus libres.
    decor=images[-1].copy();x,y=positions[-1]
    for oy,ox in np.argwhere(motif>=0):
        gx,gy=x+ox,y+oy;decor[gy,gx]=-1
        for g,p in reversed(list(zip(images[:-1],positions[:-1]))):
            if p is None:continue
            rx,ry=gx-p[0],gy-p[1]
            if not(0<=ry<motif.shape[0] and 0<=rx<motif.shape[1] and motif[ry,rx]>=0):
                decor[gy,gx]=g[gy,gx];break
    depart=positions[-1];connues=set(p for p in positions if p is not None)
    file=deque([(depart,[])]);vus={depart};limite=decor.size
    while file and len(vus)<=limite:
        pos,route=file.popleft()
        if route and (pos in cibles if cibles is not None else pos not in connues):
            return {'actions':[route[0]],'predictions':[[]],'modeles':[],
              'origine':'accord_gardes_navigation','statut':'experience_conditionnelle',
              'but':'inconnu','risque':'inconnu','route_acces_hypothetique':route,
              'cible_nouveaute':list(pos),'gardes_provisoires':gardes,
              'portee_garde':'valeurs_non_observees_hypothese' if explorer_inconnus else 'accord_candidats',
              'contrat_prediction_partielle':{'action':route[0],'objets':{'motif':motif.tolist()},
               'position_avant':list(depart),'position_candidate':[depart[i]+mouvements[route[0]][i] for i in (0,1)],
               'attributs':['position_visible'],'statut':'garde_inconnue_experience' if explorer_inconnus else 'accord_gardes_provisoires',
               'but_certifie':False,'abstentions':['autres_objets','relation_clic','but','images_intermediaires']}}
        for a,d in sorted(mouvements.items()):
            if a not in offre:continue
            cible=(pos[0]+d[0],pos[1]+d[1])
            if cible in vus or min(cible)<0 or cible[0]+motif.shape[1]>decor.shape[1] or cible[1]+motif.shape[0]>decor.shape[0]:continue
            valeurs=[int(decor[cible[1]+g['offset'][1],cible[0]+g['offset'][0]]) for g in gardes]
            if not all(v in g['permis'] or (explorer_inconnus and v>=0 and v not in g['bloques_observes']) for v,g in zip(valeurs,gardes)):continue
            vus.add(cible);file.append((cible,route+[a]))
    if cibles and not explorer_inconnus:
        return proposer(images,actions,motif,offre,positions_connues,recalages,cibles,explorer_inconnus=True)
    return None
