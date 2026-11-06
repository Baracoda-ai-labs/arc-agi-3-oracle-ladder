"""Hypothèses bornées de remplissage cyclique, apprises sur films observés."""
from collections import Counter
import numpy as np
from chrysalide.arc3.films import composantes


def apprendre(images,films,actions,region_yx,classes):
    images=list(map(np.asarray,images));region=np.zeros(images[0].shape,bool)
    region[tuple(np.array(region_yx).T)]=True
    resultats=[]
    for composante in composantes(region):
        ij=tuple(np.array([(y,x) for x,y in composante]).T)
        capacite=len(composante)
        if any(not np.isin(g[ij],classes).all() for g in images):continue
        for couleur in classes:
            comptes=[int(np.count_nonzero(g[ij]==couleur)) for g in images]
            positifs=[b-a for a,b in zip(comptes,comptes[1:]) if b>a]
            if not positifs:continue
            pas=Counter(positifs).most_common(1)[0][0]
            if capacite%pas or any((a+pas)%capacite!=b for a,b in zip(comptes,comptes[1:])):continue
            resets=[k for k,(a,b) in enumerate(zip(comptes,comptes[1:])) if b<a]
            if not resets or any(not any(np.count_nonzero(np.asarray(f)[ij]==couleur)==capacite for f in films[k]) for k in resets):continue
            enveloppe=set(composante)
            for k in resets:
                for f in films[k]:
                    for comp in composantes(np.asarray(f)==couleur):
                        if set(comp)&set(composante):enveloppe.update(comp)
            resultats.append({'enveloppe_saturation_observee_yx':[[y,x] for x,y in sorted(enveloppe)],
                'enveloppe_non_certifiee':True,'region_yx':list(map(list,zip(*ij))),'classe':int(couleur),'capacite':capacite,
                'pas':pas,'periode_candidate':capacite//pas,'compte_courant':comptes[-1],
                'comptes_observes':comptes,'resets_observes':[k+1 for k in resets],
                'commandes_observees':sorted(set(actions)),'provisoire':True,
                'causalite_certifiee':False,'animation_extension_non_modelee':True})
    return resultats


def prevoir(hypotheses,action):
    if not hypotheses or any(action not in h['commandes_observees'] for h in hypotheses):return None
    return [{'classe':h['classe'],'region_yx':h['region_yx'],
        'compte':(h['compte_courant']+h['pas'])%h['capacite'],
        'saturation_attendue':h['compte_courant']+h['pas']>=h['capacite']} for h in hypotheses]
