"""Une suite reste une proposition : validation sur le descendant et l'image courante."""
import copy
import numpy as np


def reprendre(repares, attente, resultats, sources, image):
    owner=attente.get('modele_plan');suite=attente.get('suite_plan')
    if not owner or not suite:return []
    if not any(r.get('nom')==owner and r.get('statut')=='modele_refute' for r in resultats):return []
    rapports=[]
    for nom,c in repares.items():
        # Les réparateurs nomment un descendant « source/operateur ». Le plus
        # proche parent initial évite d'attribuer la réparation d'un autre modèle.
        parents=[s for s in sources if nom.startswith(s+'/')]
        if not parents or max(parents,key=len)!=owner:continue
        rec={'type':'suite_apres_reparation','depuis':owner,'modele':nom,'longueur':len(suite)}
        rapports.append(rec)
        if c.refute or getattr(c,'but_inconnu',False):
            rec['statut']='modele_ou_but_non_admis';continue
        if not c.grilles or not np.array_equal(c.grilles[-1],image):
            rec['statut']='etat_courant_different';continue
        seq=copy.deepcopy(suite)
        valide,preuve=c.verifier_plan(seq)
        if not valide:
            rec.update(statut='suite_refusee',preuve=preuve);continue
        adoption=c.adopter_plan(seq,origine='suite_revalidee_apres_reparation')
        rec.update(statut=adoption.get('statut'),preuve=preuve)
    return rapports
