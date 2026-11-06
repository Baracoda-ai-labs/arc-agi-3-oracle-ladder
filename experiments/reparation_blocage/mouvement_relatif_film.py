"""Vérifier une relation relative dans le film sans attribuer le référentiel à une caméra."""
import numpy as np
from objets_identites import occurrences,suivre_motif


def verifier(avant,film,motif,forme,associations):
    from relation_clic_observee import positions
    images=[np.asarray(avant),*map(np.asarray,film)];motif=np.asarray(motif)
    n=len(occurrences(images[0],motif))
    if n<2:return {'statut':'hors_portee_identites_multiples','associations':[]}
    try:series=suivre_motif(images,motif,n)
    except ValueError as e:return {'statut':'identites_ambigues','raison':str(e),'associations':[]}
    resultats=[]
    for association in associations:
        p=tuple(association['support']);f=tuple(association['independante'])
        if p not in series[0]:continue
        piste=series[0].index(p);offset=(f[0]-p[0],f[1]-p[1])
        supports=[s[piste] for s in series]
        maintien=[(q[0]+offset[0],q[1]+offset[1]) in positions(g,frozenset(map(tuple,forme))) for q,g in zip(supports,images)]
        resultats.append({'support_initial':list(p),'offset':list(offset),'supports':list(map(list,supports)),
            'relation_visible_par_image':maintien,'deplacement_visible':any(q!=p for q in supports),
            'relation_relative_verifiee':all(maintien) and any(q!=p for q in supports),
            'contenance_certifiee':False,'causalite_certifiee':False})
    return {'statut':'film_observe','images':len(images),'associations':resultats,
        'referentiel':'camera_ou_mouvement_decor_non_departages','but_certifie':False}
