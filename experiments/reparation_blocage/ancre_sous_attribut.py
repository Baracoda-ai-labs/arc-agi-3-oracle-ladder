"""Ancre partielle sous modification locale prédite, sans effacer un changement arbitraire."""
import numpy as np
from objets_identites import occurrences


def retrouver(image,motif,position,contrat):
    if not contrat:return None
    x,y=position;dx,dy=contrat['destination'];forme=contrat['objets']['forme']
    masque=np.asarray(motif).copy();retires=[]
    for ox,oy in forme:
        mx,my=dx+ox-x,dy+oy-y
        if 0<=my<masque.shape[0] and 0<=mx<masque.shape[1] and masque[my,mx]>=0:
            retires.append([int(mx),int(my)]);masque[my,mx]=-1
    if not retires or np.count_nonzero(masque>=0)<4:return None
    ys,xs=np.where(masque>=0)
    # Garder l'étendue entière : aucune nouvelle ancre induite par une forme rétrécie.
    yy,xx=np.where(np.asarray(motif)>=0)
    if (min(xs),max(xs),min(ys),max(ys))!=(min(xx),max(xx),min(yy),max(yy)):return None
    lieux=occurrences(image,masque)
    if lieux!=[tuple(position)]:return None
    return {'position':list(position),'motif_stable':masque.tolist(),'pixels_attribut':retires,
            'preuve':'ancre_unique_sur_partie_hors_destination_predite','identite':'provisoire'}
