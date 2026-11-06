"""Mémoire de mécanismes provisoires, distincte de l'instance et des preuves locales."""
import copy
from dataclasses import dataclass,field
from collections import Counter
import numpy as np
from objets_variables import ObjetsVariables
from chrysalide.arc3.moteur import _composantes,_sprite
from perception_guidee import PerceptionGuidee

@dataclass
class ModeleJeu:
    famille: str
    acquis: object
    provenance: dict
    promotion_durable: bool = False
    contexte_selection: dict = field(default_factory=dict)
    commandes_observees: set = field(default_factory=set)

    def installer(self,agent):
        if self.famille=='empreintes':
            from transfert_empreintes import lier
            agent.transfert_empreintes=(self.acquis,lier(self.acquis,agent.images[0]))
        elif self.famille=='objets':
            source,programme=self.acquis
            base_source=source
            while hasattr(base_source,'base'):base_source=base_source.base
            # Le transfert géométrique ne sait réécrire que ce contrat de base.
            # Refuser les réparations/terminaisons non prises en charge avant mutation.
            if type(base_source) is not ObjetsVariables:
                raise ValueError('Perception source non transférable par cette capacité')
            if not any(programme == base_source.programme(but) for but in base_source.buts):
                raise ValueError('Programme acquis non réaffectable : lois ou but hors contrat ObjetsVariables')
            vue,diag=reaffecter_objets(source,agent.images[0])
            base=vue
            while hasattr(base,'base'):base=base.base
            for i,but in enumerate(base.buts):
                c=agent._chaine(vue,base.programme(but))
                agent._admettre('transfert_objets_'+str(i),c)
            agent.journal.append({'type':'reaffectation_instance',**diag})
            if not agent.chaines:raise ValueError('Aucune instance de modèle transféré admise')
        else:raise ValueError('Famille sans réaffectation implémentée')
        # Historique d’observations, jamais commandes déduites du programme ou en attente.
        agent.commandes_connues = set(getattr(agent, "commandes_connues", ())) | set(
            getattr(self, "commandes_observees", ()))
        agent.reconstruction=False
        agent.memoire_jeu=self
        agent.journal.append({'type':'modele_jeu_transfere','famille':self.famille,'provenance':self.provenance,'promotion_durable':False})

def reaffecter_objets(source,image):
    layers=[];base=source
    while hasattr(base,'base'):
        layers+=getattr(base,'points',[]);base=base.base
    if type(base) is not ObjetsVariables:raise ValueError('Perception source non transférable par cette capacité')
    v=copy.deepcopy(base);v._positions_connues={};v.fond=Counter(image.ravel().tolist()).most_common(1)[0][0]
    clean=v.vue(image);sprites=[_sprite(o) for o in _composantes(clean,v.fond)]
    mobiles=[];positions=[]
    for motif in base.mobiles:
        colors=set(map(int,motif[motif>=0]));major=Counter(motif[motif>=0].tolist()).most_common(1)[0][0]
        candidates=[s for s in sprites if np.count_nonzero(s['pixels']==major)>=3 and 0<s['x'] and 0<s['y'] and s['x']+s['pixels'].shape[1]<image.shape[1] and s['y']+s['pixels'].shape[0]<image.shape[0]]
        if len(candidates)!=1:raise ValueError('Rôle mobile ambigu : réexaminer la perception')
        s=candidates[0];h,w=s['pixels'].shape;x,y=s['x'],s['y'];patch=clean[y:y+h,x:x+w].copy().astype(np.int16);patch[~np.isin(patch,list(colors))]=-1
        mobiles.append(patch);positions.append((x,y))
    v.mobiles=mobiles;v.initiales=positions
    decor=clean.copy()
    for motif,(x,y) in zip(mobiles,positions):decor[y:y+motif.shape[0],x:x+motif.shape[1]][motif>=0]=v.fond
    v.decor=decor;v.statiques=[_sprite(o) for o in _composantes(decor,v.fond)]
    v.buts=[(i,j) for i,m in enumerate(v.mobiles) for j,s in enumerate(v.statiques) if s['pixels'].shape==m.shape and np.array_equal(s['pixels']>=0,m>=0)]
    if not v.buts:raise ValueError('But de correspondance non réaffecté')
    # Les détails appris sont relatifs à la cible, jamais aux coordonnées de N1.
    pts=[]
    for yy,xx,color in layers:
        for _,j in base.buts:
            old=base.statiques[j];dy,dx=yy-old['y'],xx-old['x']
            if 0<=dy<old['pixels'].shape[0] and 0<=dx<old['pixels'].shape[1]:
                for _,jj in v.buts:
                    new=v.statiques[jj]
                    if dy<new['pixels'].shape[0] and dx<new['pixels'].shape[1] and new['pixels'][dy,dx]==color:pts.append((new['y']+dy,new['x']+dx,color))
    result=PerceptionGuidee(v,pts) if pts else v
    return result,{'regles_mouvement_reapprises':0,'formes_source':[list(m.shape) for m in base.mobiles],'formes_instance':[list(m.shape) for m in v.mobiles],'buts_candidats':len(v.buts),'details_reaffectes':len(set(pts))}
