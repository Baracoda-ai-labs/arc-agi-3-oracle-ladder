"""Affordance visuelle candidate dans une destination déjà occupée visuellement."""
import numpy as np


def candidat(avant,apres,destination,forme):
    x,y=destination;forme=set(map(tuple,forme));a=np.asarray(avant);b=np.asarray(apres)
    pixels=[(x+dx,y+dy) for dx,dy in forme if 0<=y+dy<a.shape[0] and 0<=x+dx<a.shape[1] and a[y+dy,x+dx]!=b[y+dy,x+dx]]
    if len(pixels)<2:return None
    couleurs={int(b[yy,xx]) for xx,yy in pixels}
    if len(couleurs)!=1:return None
    cx=sum(xx for xx,yy in pixels)/len(pixels);cy=sum(yy for xx,yy in pixels)/len(pixels)
    xx,yy=min(pixels,key=lambda p:((p[0]-cx)**2+(p[1]-cy)**2,p))
    return {'x':xx,'y':yy,'c':next(iter(couleurs)),'n':len(pixels),
            'preuve':'difference_locale_sur_destination_apres_selection',
            'pixels_modifies':[list(p) for p in pixels],
            'portee':'affordance_candidate_pas_preuve_de_mouvement'}
