"""Trous explicites dans un suivi de motifs ; aucune transition inventée au trou."""
from objets_identites import occurrences,suivre_motif

def suivre(images,motif,cardinalite):
    valides=[i for i,g in enumerate(images) if len(occurrences(g,motif))==cardinalite]
    if not valides or valides[-1]!=len(images)-1:raise ValueError('Identités courantes non observées')
    pistes=suivre_motif([images[i] for i in valides],motif,cardinalite)
    resultat=[None]*len(images)
    for i,p in zip(valides,pistes):resultat[i]=p
    return resultat,{'images_non_resolues':[i for i,p in enumerate(resultat) if p is None],
        'identite':'hypothese_continuite_minimale_unique','transitions_traversant_trou':'non_utilisables'}
