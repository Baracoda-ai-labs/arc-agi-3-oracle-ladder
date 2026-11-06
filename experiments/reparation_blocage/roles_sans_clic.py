"""Hypothèse de rôle commandé issue du mouvement et d'un attribut de coque."""
import numpy as np
from roles_observes import PerceptionRoles


def amorcer(images,actions,films=None):
    limite=next((i for i,a in enumerate(actions) if isinstance(a,list)),len(actions))
    # Dernier préfixe où le mobile conserve son apparence, avant le contact éventuel.
    for n in range(limite,0,-1):
        try:
            base=PerceptionRoles(images[:n+1],actions[:n],films=films[:n] if films is not None else None)
        except ValueError:
            continue
        if len(base.mobiles)!=1:continue
        m=base.mobiles[0];h,w=m.shape
        if h<3 or w<3:continue
        g=base.vue(images[0]);fen=np.lib.stride_tricks.sliding_window_view(g,(h,w))
        erreurs=(fen!=m).sum(axis=(-2,-1));indices={};valeurs=set()
        for y,x in np.argwhere(erreurs==1):
            iy,ix=map(int,np.argwhere(fen[y,x]!=m)[0])
            if not (0<iy<h-1 and 0<ix<w-1):continue
            indices[iy,ix]=True;valeurs.add(int(fen[y,x,iy,ix]))
        if len(indices)!=1 or len(valeurs)!=1:continue
        my,mx=next(iter(indices));inactif=next(iter(valeurs))
        return base,m,(my,mx),inactif,{'prefixe_mobile':n,
            'role_commande':'hypothese_depuis_mouvement','selection_clic':'non_observee',
            'marqueur_repos':'hypothese_identique_a_inactif','promotion_durable':False}
    raise ValueError('Pas de rôle par mouvement/coques à attribut unique')
