"""Décor dévoilé et franchissement observé ; aucune identité de jeu."""
import copy

import numpy as np
from objets_variables import ObjetsVariables, localiser

from chrysalide.arc3.moteur import _composantes, _sprite


class PerceptionRoles(ObjetsVariables):
    def __init__(self,images,actions,decor_revele=True,roles=True,clics_negatifs=False,films=None):
        super().__init__(images,actions,clics_negatifs=clics_negatifs,films=films)
        propres=[self.vue(g) for g in images]
        positions=[[localiser(g,m) for m in self.mobiles] for g in propres]
        masques=[]
        for pos in positions:
            occ=np.zeros((64,64),bool)
            for m,(x,y) in zip(self.mobiles,pos):
                occ[y:y+m.shape[0],x:x+m.shape[1]]|=m>=0
            masques.append(occ)
        self.preuves_decor=[];self.inconnus_decor=[]
        if decor_revele:
            for y,x in np.argwhere(masques[0]):
                vus=[(t,int(g[y,x])) for t,g in enumerate(propres) if not masques[t][y,x]]
                valeurs={c for _,c in vus}
                if len(valeurs)==1:
                    self.decor[y,x]=next(iter(valeurs))
                    self.preuves_decor.append({'y':int(y),'x':int(x),'vues':vus})
                else:
                    self.inconnus_decor.append([int(y),int(x)])
            self.statiques=[_sprite(o) for o in _composantes(self.decor,self.fond)]
        # La couleur de fond n'est pas déclarée marchable par simple omission.
        fond=np.where(self.decor==self.fond,self.fond,-1).astype(np.int16)
        self.statiques.append({'pixels':fond,'x':0,'y':0,'couche':0})
        self.buts=[]
        for i,m in enumerate(self.mobiles):
            for j,s in enumerate(self.statiques):
                px=s['pixels']
                if px.shape==m.shape and np.array_equal(px>=0,m>=0): self.buts.append((i,j))
        self.franchis={};self.roles_actifs=roles
        for t in range(1,len(propres)):
            for i,m in enumerate(self.mobiles):
                if positions[t][i]==positions[t-1][i]: continue
                x,y=positions[t][i];yy,xx=np.nonzero(m>=0)
                for j,s in enumerate(self.statiques):
                    xs,ys=xx+x-s['x'],yy+y-s['y'];h,w=s['pixels'].shape
                    dedans=(xs>=0)&(xs<w)&(ys>=0)&(ys<h)
                    if np.any(s['pixels'][ys[dedans],xs[dedans]]>=0):
                        self.franchis.setdefault(j,[]).append({'transition':t,'mobile':i})

    def signature_observation(self):
        return {**super().signature_observation(),'reconstruction':'pixels_devoiles',
                'preuves_decor':self.preuves_decor,'inconnus_decor':self.inconnus_decor,
                'franchis':self.franchis,'roles_actifs':self.roles_actifs}

    def programme(self,cible=None):
        p=copy.deepcopy(super().programme(cible))
        def reviser(x):
            if isinstance(x,list):
                if len(x)==5 and x[0]=='libre' and isinstance(x[-1],dict):
                    tags={f'statique_{j}' for j in self.franchis}
                    if self.roles_actifs and x[-1].get('tag') in tags: return True
                return [reviser(v) for v in x]
            if isinstance(x,dict): return {k:reviser(v) for k,v in x.items()}
            return x
        return reviser(p)
