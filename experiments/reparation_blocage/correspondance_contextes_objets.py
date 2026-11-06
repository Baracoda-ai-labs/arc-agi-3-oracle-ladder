"""Identités inter-contextes depuis commutations observées, puis réaffectation exacte."""
import copy
import numpy as np
from objets_variables import ObjetsVariables,localiser
from perception_guidee import PerceptionGuidee
from diagnostic_contexte_transfert import marqueurs
from revision_garde_commune import parametrer
from chaine_coherente import Chaine


def _base(v):
    points=[]
    while hasattr(v,'base'):
        if type(v) is not PerceptionGuidee:raise ValueError('calque_non_supporte')
        points+=v.points;v=v.base
    if type(v) is not ObjetsVariables:raise ValueError('objets_non_supportes')
    return v,points


def reaffecter_observation(source,image):
    """Conserve lois et indices ; seuls positions d'instance et calques relatifs changent."""
    diag={'admis':False,'provisoire':True,'mouvements_reappris':0,'but_ajoute':False}
    try:
        if source.refute or source.rejouer()[1] is None:raise ValueError('source_non_admissible')
        base,points=_base(source.perception)
        choix=[]
        for but in [None,*base.buts]:
            p=base.programme(but)
            if p==source.programme:choix.append((but,False))
            if but is not None and parametrer(base,p)==source.programme:choix.append((but,True))
        if len(choix)!=1:raise ValueError('programme_hors_contrat')
        but,garde=choix[0]
        v=copy.deepcopy(base);v._positions_connues={};image=np.asarray(image)
        if image.shape!=np.asarray(source.grilles[0]).shape:raise ValueError('dimensions_differentes')
        propre=v.vue(image)
        mobiles=[localiser(propre,m) for m in v.mobiles]
        statiques=[localiser(propre,s['pixels']) for s in v.statiques]
        v.initiales=mobiles
        for s,(x,y) in zip(v.statiques,statiques):s['x'],s['y']=x,y
        v.decor=propre.copy()
        for m,(x,y) in zip(v.mobiles,mobiles):
            v.decor[y:y+m.shape[0],x:x+m.shape[1]][m>=0]=v.fond
        nouveaux_points=[]
        for y,x,couleur in points:
            supports=[]
            for j,s in enumerate(base.statiques):
                dy,dx=y-s['y'],x-s['x'];px=s['pixels']
                if 0<=dy<px.shape[0] and 0<=dx<px.shape[1] and px[dy,dx]==couleur:
                    supports.append((j,dy,dx))
            if len(supports)!=1:raise ValueError('ancrage_calque_ambigu')
            j,dy,dx=supports[0];s=v.statiques[j]
            nouveaux_points.append((s['y']+dy,s['x']+dx,couleur))
        vue=PerceptionGuidee(v,nouveaux_points) if points else v
        programme=copy.deepcopy(source.programme)
        # Seul le but reconnu est réancré à sa cible ; aucune condition nouvelle.
        if but is not None:
            ancien=base.programme(but)['regles'][-1];nouveau=v.programme(but)['regles'][-1]
            indices=[i for i,r in enumerate(programme['regles']) if r==ancien]
            if len(indices)!=1:raise ValueError('but_non_unique')
            programme['regles'][indices[0]]=nouveau
        c=Chaine(vue,programme,[image.tolist()],[],source.actions)
        controle,state=c.rejouer()
        if state is None or not all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
            raise ValueError('instance_non_admissible')
        if not np.array_equal(vue.rendu(state[1]),vue.vue(image)):raise ValueError('rendu_non_exact')
        c.activer_atms()
        diag.update(admis=True,controle=controle,positions_mobiles=mobiles,positions_statiques=statiques,
            but_conserve=but is not None,garde_commune_conservee=garde,
            programme_identique=programme==source.programme,calques=len(nouveaux_points),
            portee='image_initiale_observee_seulement',masque_herite_provisoire=True)
        return c,diag
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        return None,{**diag,'refus':str(exc)}


def _roles(c):
    b,_=_base(c.perception)
    return [(('mobile',i),m,xy) for i,(m,xy) in enumerate(zip(b.mobiles,b.initiales))]+[
        (('statique',i),s['pixels'],(s['x'],s['y'])) for i,s in enumerate(b.statiques)]


def apprendre(principal,alternatif,paires):
    """paires : (image_principale, image_alternative), transitions réellement observées."""
    preuves=[];correspondance=None
    if not paires:return None,{'refus':'aucune_commutation_observee'}
    for index,(avant,apres) in enumerate(paires):
        cp,dp=reaffecter_observation(principal,avant)
        ca,da=reaffecter_observation(alternatif,apres)
        if cp is None or ca is None:return None,{'refus':'paire_non_reaffectable','paire':index,'principal':dp,'alternatif':da}
        bp,_=_base(cp.perception);ba,_=_base(ca.perception)
        hud=set(bp.hud)&set(ba.hud)
        changes={tuple(map(int,p)) for p in np.argwhere(np.asarray(avant)!=np.asarray(apres))}-hud
        marqueurs_communs=[{p for hs in marqueurs(im).values() for ps in hs.values() for p in ps} for im in (avant,apres)]
        if not changes or not changes<=marqueurs_communs[0]&marqueurs_communs[1]:
            return None,{'refus':'commutation_non_limitee_aux_marqueurs','paire':index}
        mapping=[]
        for role,m,(x,y) in _roles(cp):
            compatibles=[]
            for autre,n,xy in _roles(ca):
                if xy!=(x,y) or m.shape!=n.shape:continue
                stable=np.ones(m.shape,dtype=bool)
                for yy,xx in changes:
                    if y<=yy<y+m.shape[0] and x<=xx<x+m.shape[1]:stable[yy-y,xx-x]=False
                if (stable & (m>=0)).any() and np.array_equal(m[stable],n[stable]):compatibles.append(autre)
            if len(compatibles)!=1:return None,{'refus':'identite_ambigue','paire':index,'role':role}
            mapping.append((role,compatibles[0]))
        if len(set(b for _,b in mapping))!=len(mapping) or len(mapping)!=len(_roles(ca)):
            return None,{'refus':'correspondance_non_bijective','paire':index}
        if correspondance is not None and correspondance!=mapping:return None,{'refus':'correspondances_contradictoires'}
        correspondance=mapping;preuves.append({'paire':index,'pixels_marqueurs_changes':len(changes)})
    return correspondance,{'admis':True,'mecanisme_ontologique':'selection_marqueur',
        'portee':'identites_sur_commutations_observees','commutation_dynamique_apprise':False,
        'provisoire':True,'preuves':preuves}
