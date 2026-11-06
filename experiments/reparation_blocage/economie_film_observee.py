"""Population visible et attributs du film ; aucune loi de consommation ou de défaite."""
import numpy as np
from chrysalide.arc3.moteur import _composantes
from ontologie_extensible import decrire_economie


def composantes(image):
    g=np.asarray(image);fond=int(np.bincount(g.ravel()).argmax())
    return _composantes(g,fond)


def analyser(avant,film,forme,issue='continue'):
    forme=frozenset(map(tuple,forme));gs=[np.asarray(avant),*map(np.asarray,film)]
    if len(gs)<2:raise ValueError('Film vide')
    series=[]
    for g in gs:
        series.append([{'couleur':int(c),'x':int(x),'y':int(y)}
            for c,f,x,y in composantes(g) if f==forme])
    recolorations=[];variations=[]
    for i,(a,b) in enumerate(zip(series,series[1:]),1):
        pa={(o['x'],o['y']):o['couleur'] for o in a};pb={(o['x'],o['y']):o['couleur'] for o in b}
        rs=[{'position':list(p),'avant':pa[p],'apres':pb[p]} for p in sorted(pa.keys()&pb.keys()) if pa[p]!=pb[p]]
        if rs:recolorations.append({'image':i,'changements':rs,'identite':'compatibilite_forme_position_non_causale'})
        if len(a)!=len(b):variations.append({'image':i,'avant':len(a),'apres':len(b),
            'interpretation':'population_visible_varie; occlusion/fusion/transformation/consommation indépartagées'})
    nouvelles=set(np.unique(gs[-1]).tolist())-set(np.unique(gs[0]).tolist())
    nouveaux=[]
    for c,f,x,y in composantes(gs[-1]):
        if c not in nouvelles:continue
        cells={(y+dy,x+dx) for dx,dy in f}
        apparition=next(i for i,g in enumerate(gs) if any(int(g[yy,xx])==c for yy,xx in cells))
        nouveaux.append({'couleur':int(c),'surface':len(f),'x':int(x),'y':int(y),
            'forme':sorted(map(list,f)),'premiere_image_aux_positions_finales':apparition,
            'role':'indicateur_ou_objet_inconnu'})
    return {'forme_reference':sorted(map(list,forme)),'images_natives':len(film),'occurrences':series,
        'population_visible_avant':len(series[0]),'population_visible_apres':len(series[-1]),
        'variations_population':variations,'recolorations':recolorations,'nouveaux_composants':nouveaux,
        'economie':decrire_economie(),'issue_observee':issue,'consommation_validee':False,
        'defaite_validee':issue=='defaite','victoire_validee':issue in ('niveau','victoire'),
        'identites_individuelles_validees':False,'portee':'film_observe_pas_simulateur'}


def proposer_indicateur(rapport,offre,actions_deja=()):
    """Sonde d'affordance, pas une action réputée sûre ni une conclusion sur l'issue."""
    if 6 not in offre or rapport['issue_observee']!='continue':return None
    deja={tuple(a) for a in actions_deja if isinstance(a,(tuple,list))}
    for o in sorted(rapport['nouveaux_composants'],key=lambda o:-o['surface']):
        # Choisir un pixel du composant proche de son centre ; pas un trou de la forme.
        f=o['forme'];cx=sum(x for x,y in f)/len(f);cy=sum(y for x,y in f)/len(f)
        dx,dy=min(f,key=lambda p:((p[0]-cx)**2+(p[1]-cy)**2,p[1],p[0]))
        a=['clic',o['x']+dx,o['y']+dy]
        if tuple(a) in deja:continue
        return {'actions':[a],'predictions':[[]],'but':'inconnu','risque':'inconnu',
            'statut':'experience_conditionnelle','origine':'indicateur_nouveau_film',
            'question':'Ce nouvel élément est-il interactif et change-t-il état, commandes ou issue ?',
            'hypotheses':['indication passive','commande contextuelle interactive'],
            'preuve':o,'cout_coup':1,'consommation_validee':False,
            'attention':'Peut déclencher changement de scène ou tentative ; aucun reset implicite présumé.'}
    return None
