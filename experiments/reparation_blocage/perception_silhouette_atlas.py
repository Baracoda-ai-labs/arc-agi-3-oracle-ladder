"""Atlas de silhouettes observées : identité candidate, orientation conservée."""
from collections import Counter
import os
import numpy as np
from navigation_gravite_visible import NavigationVisible
from perception_navigation import candidats
from chrysalide.arc3.moteur import MoteurFormel,NOMS
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.masque import Masque


def atlas(images,actions):
    if not actions or any(not isinstance(a,(int,np.integer)) for a in actions):raise ValueError('Commandes directionnelles observées requises')
    nav=NavigationVisible(images,actions);nav.perception_connexe=True
    positions=[];motifs=[]
    for image in images:
        g=np.asarray(image);ps=candidats(nav,g)
        if len(ps)!=1:raise ValueError('Silhouette ambiguë ou absente')
        positions.append(ps[0]);m=np.isin(g,list(nav.palette));y,x=np.nonzero(m)
        motifs.append(np.where(m,g,-1)[y.min():y.max()+1,x.min():x.max()+1])
    preuves=[]
    for k,(a,b) in enumerate(zip(motifs,motifs[1:])):
        meme=np.array_equal(a,b);miroir=np.array_equal(a[:,::-1],b)
        if not meme and not miroir:raise ValueError('Orientation hors atlas miroir')
        preuves.append({'coup':k+1,'miroir_horizontal':bool(miroir and not meme),
            'orientation_identique':bool(meme),'deplacement_xy':[v-u for u,v in zip(positions[k],positions[k+1])],
            'identite_provisoire':True})
    return nav,positions,motifs,preuves


class SilhouetteAtlas(MoteurFormel):
    def __init__(self,images,actions):
        gs=list(map(np.asarray,images));self.nav,positions,motifs,self.preuves=atlas(gs,actions)
        self.fond=Counter(gs[0].ravel().tolist()).most_common(1)[0][0]
        masque=Masque(court=True)
        for a,b in zip(gs,gs[1:]):masque.observer(a.tolist(),b.tolist())
        from jauges_observees import jauges_validees
        jauges,self.preuves_jauge=jauges_validees(gs,actions)
        self.hud=masque.cellules() | jauges;self.pas=self.nav.pas
        s=self.pas;boites=[(x-s//2,y-s//2) for x,y in positions]
        occ=[]
        for x,y in boites:
            if min(x,y)<0 or y+s>gs[0].shape[0] or x+s>gs[0].shape[1]:raise ValueError('Silhouette au bord non couverte')
            m=np.zeros(gs[0].shape,bool);m[y:y+s,x:x+s]=True;occ.append(m)
        self.decor=self.vue(gs[0]);self.contradictions_statiques=[]
        for y,x in np.ndindex(gs[0].shape):
            if (y,x) in self.hud:continue
            valeurs={int(g[y,x]) for g,m in zip(gs,occ) if not m[y,x]}
            if not valeurs:raise ValueError('Fond sous silhouette non observé')
            if len(valeurs)>1:self.contradictions_statiques.append([y,x])
            else:self.decor[y,x]=next(iter(valeurs))
        self.opaque_observe = os.environ.get("CHRYS_ATLAS_OPAQUE_OBSERVE") == "1"
        self.variantes=[];self.empreintes=[];orientations=[]
        for g,(x,y),motif in zip(gs,boites,motifs):
            px=g[y:y+s,x:x+s].copy()
            # Hypothèse explicite : le rectangle observé est opaque. Ne pas inférer
            # la transparence du seul fait qu’un pixel égale le fond à cet endroit.
            if not self.opaque_observe:
                px=np.where(px!=self.decor[y:y+s,x:x+s],px,-1)
            indice=next((i for i,m in enumerate(self.empreintes) if np.array_equal(m,motif)),None)
            if indice is None:indice=len(self.variantes);self.variantes.append(px);self.empreintes.append(motif)
            elif not np.array_equal(px,self.variantes[indice]):raise ValueError('Même orientation, rendu variable non expliqué')
            orientations.append(indice)
        self.lois={}
        for k,action in enumerate(actions):
            loi=(*[b-a for a,b in zip(boites[k],boites[k+1])],orientations[k+1])
            if action in self.lois and self.lois[action]!=loi:raise ValueError('Effet contextuel non expliqué')
            self.lois[int(action)]=loi
        self.buts=[]

    def vue(self,g):
        a=np.asarray(g).copy()
        for y,x in self.hud:a[y,x]=self.fond
        return a

    def scene(self,g):
        ps=candidats(self.nav,np.asarray(g))
        if len(ps)!=1:raise ValueError('Silhouette ambiguë ou absente')
        x,y=ps[0];s=self.pas;m=np.isin(g,list(self.nav.palette));yy,xx=np.nonzero(m)
        motif=np.where(m,g,-1)[yy.min():yy.max()+1,xx.min():xx.max()+1]
        ids=[i for i,q in enumerate(self.empreintes) if np.array_equal(motif,q)]
        if len(ids)!=1:raise ValueError('Orientation non observée')
        i=ids[0]
        return Scene(np.asarray(g).shape,self.fond,self.fond,[
            {'x':0,'y':0,'pixels':self.decor.copy(),'couche':0,'tags':['decor']},
            {'x':x-s//2,'y':y-s//2,'pixels':self.variantes[i].copy(),'couche':1,'tags':['silhouette'],
             'attrs':{'orientation':i,**{f'motif_{j}':q.tolist() for j,q in enumerate(self.variantes)}}}])

    def programme(self):
        return {'mode':'lois','etat':{},'regles':[
            {'nom':f'silhouette_{a}','phase':0,'quand':['=',['action'],NOMS[a]],
             'alors':[['pour','$o',['objets',{'tag':'silhouette'}],[
                 ['poser_motif','$o',['attr','$o',f'motif_{ori}']],
                 ['poser_attr','$o','orientation',ori],['deplacer','$o',dx,dy]]]]}
            for a,(dx,dy,ori) in self.lois.items()]}

    def signature_observation(self):
        return {'methode':'silhouette_atlas_observe','orientations':[p.tolist() for p in self.variantes],
            'decor':self.decor.tolist(),'hud':sorted(self.hud),'preuves':self.preuves,
            'contradictions_statiques':self.contradictions_statiques,'preuves_jauge':self.preuves_jauge,'but_inconnu':True}
