"""Diagnostic local par dépendances des contrats ; aucun identifiant de jeu."""
from collections import Counter,defaultdict
import copy
import numpy as np
from scipy.ndimage import label
from chrysalide.langue.ontologie_formelle import MECANISMES,TYPES_ECART,separer_pour_transfert
from atms import ATMS

def marqueurs(image):
    im=np.asarray(image);out=defaultdict(lambda:defaultdict(list))
    for color in np.unique(im):
        cc,n=label(im==color)
        for k in range(1,n+1):
            pts=np.argwhere(cc==k)
            if len(pts)!=1:continue
            y,x=map(int,pts[0])
            if not (0<y<im.shape[0]-1 and 0<x<im.shape[1]-1):continue
            ns=[int(im[y+dy,x+dx]) for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]]
            if len(set(ns))==1:out[int(color)][ns[0]].append((y,x))
    return {c:dict(h) for c,h in out.items()}

def contexte_source(images):
    # Hypothèse de marqueur : points enclavés présents sur tous les états source.
    obs=[marqueurs(im) for im in images]
    colors=set.intersection(*(set(o) for o in obs)) if obs else set()
    return {c:sorted({h for o in obs for h in o[c]}) for c in colors if all(len(o[c])==1 for o in obs)}

def diagnostiquer(chaine,modele,avant,apres,action,prediction=None):
    if 'selection' not in MECANISMES['deplacement']['lit']:return None
    base=chaine.perception
    while hasattr(base,'base'):base=base.base
    try:p0=base.positions_observees(avant);p1=base.positions_observees(apres)
    except (ValueError,AttributeError):return None
    if prediction is None:return None
    try:predicted=base.positions_observees(np.asarray(prediction))
    except ValueError:return None
    if predicted==p0 or p0!=p1:return None
    current=marqueurs(avant);candidates=[]
    for color,hosts in modele.contexte_selection.items():
        seen=current.get(color,{})
        if len(seen)==1 and not set(seen)<=set(hosts):
            candidates.append({'marqueur':color,'hotes_source':hosts,'hotes_observes':list(seen),'pixels_marqueur':sum(map(len,seen.values()))})
    if not candidates:return None
    a=ATMS();a.supposer('regles_deplacement');a.supposer('selection_instance_equivalente');a.justifier('plan_transfere',['regles_deplacement','selection_instance_equivalente']);a.interdire(['selection_instance_equivalente'])
    return {'type_ecart':'BLOCAGE','hypotheses_initiales':TYPES_ECART['BLOCAGE'][1],
            'dependance_oubliee':'selection','contrat_candidat':'selection_marqueur',
            'contrat':copy.deepcopy(MECANISMES['selection_marqueur']),
            'statut':'contexte_different_cause_a_tester','preuves':candidates,
            'transfert':separer_pour_transfert({'mecanisme':'deplacement','params':{'selection':None}}),
            'regles_conservees':a.tient('regles_deplacement',['regles_deplacement']),
            'plan_revoque':not a.tient('plan_transfere',['regles_deplacement']),
            'but':'non_refute_par_ce_constat','contexte_atms':a.rapport()}

def compatible(modele,image):
    seen=marqueurs(image)
    return bool(modele.contexte_selection) and all(len(seen.get(c,{}))==1 and set(seen[c])<=set(hosts) for c,hosts in modele.contexte_selection.items())
