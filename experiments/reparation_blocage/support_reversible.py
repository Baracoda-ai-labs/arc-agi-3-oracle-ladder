"""Hypothèse locale apprise d'un cycle visible ouvert/fermé, sans généralisation de couleur."""

import numpy as np
from hypotheses_refermeture import variantes


def apprendre(avant, ouvert, referme, action, modele, contexte):
    predictions = variantes(avant, ouvert, ouvert, action, modele)
    if not np.array_equal(referme[:-1], predictions["refermeture_locale"][0][:-1]):
        raise ValueError("Fermeture non conforme à la prédiction locale")
    mask = avant != ouvert
    mask[-1] = False
    ys, xs = np.nonzero(mask)
    return {
        "contexte": contexte,
        "action": list(action),
        "pixels_xy": np.column_stack((xs, ys)).tolist(),
        "ferme": avant[ys, xs].astype(int).tolist(),
        "ouvert": ouvert[ys, xs].astype(int).tolist(),
        "statut": "hypothese_locale_observee_dans_deux_sens",
        "transfert_autres_objets": False,
        "fermeture_sur_controle": "non_testee",
        "effet_sur_arret": "a_verifier",
        "causalite": "cycle observé après clics ; autre effet temporel non exclu par témoin dédié",
    }


def projeter(image, regle, contexte):
    if contexte != regle["contexte"]:
        return None
    xy = np.asarray(regle["pixels_xy"])
    xs, ys = xy[:, 0], xy[:, 1]
    values = image[ys, xs]
    if np.array_equal(values, regle["ferme"]):
        dest = regle["ouvert"]
    elif np.array_equal(values, regle["ouvert"]):
        dest = regle["ferme"]
    else:
        return None
    output = np.array(image, copy=True)
    output[ys, xs] = dest
    return output
