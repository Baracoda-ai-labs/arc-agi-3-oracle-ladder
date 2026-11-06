"""Recalage apparent réutilisant l'estimateur bp35 ; hypothèse, pas caméra certifiée."""
import numpy as np
from boucle_navigation_visible import decalage


def recouvrement(a,b,dx,dy):
    h,w=a.shape
    return (a[max(0,-dy):min(h,h-dy),max(0,-dx):min(w,w-dx)],
            b[max(0,dy):min(h,h+dy),max(0,dx):min(w,w+dx)])


def estimer(avant,apres,palette):
    a=np.asarray(avant);b=np.asarray(apres)
    masque=~np.isin(a,list(palette)) & ~np.isin(b,list(palette))
    erreur_zero=float(np.mean(a[masque]!=b[masque])) if masque.any() else 1.
    dy,ey=decalage(a,b,palette,bord=None);dx,ex=decalage(a.T,b.T,palette,bord=None)
    candidats=[(ex,(dx,0)),(ey,(0,dy))]
    if erreur_zero>.1 and min(ex,ey)>.1:
        # Réutiliser l'estimateur un axe sur le recouvrement déjà aligné.
        ay,by=recouvrement(a,b,0,dy)
        ax,bx=recouvrement(a,b,dx,0)
        xy,_=decalage(ay.T,by.T,palette,bord=None)
        yx,_=decalage(ax,bx,palette,bord=None)
        for vx,vy in ((xy,dy),(dx,yx)):
            aa,bb=recouvrement(a,b,vx,vy)
            mm=~np.isin(aa,list(palette)) & ~np.isin(bb,list(palette))
            if aa.size>=a.size/4 and int(mm.sum())>=max(16,a.size/10):
                candidats.append((float(np.mean(aa[mm]!=bb[mm])),(vx,vy)))
    err,d=min(candidats)
    # Prior de translation simple ; seuil explicite de réduction d'erreur, non preuve physique.
    retenu=bool(d!=(0,0) and np.isfinite(err) and err<erreur_zero/2)
    return {'translation':list(d if retenu else (0,0)), 'erreur':err,
        'erreur_sans_recalage':erreur_zero,'retenu':retenu,
        'statut':'translation_apparente_provisoire','camera_certifiee':False,
        'limite':'axes_composes_palette_masquee_heuristique_gain50pourcent_marge_non_certifiee', 'bord_HUD_implicite':False}
