"""Réversibilité d'une ouverture locale : hypothèses, pas règle ajoutée au jeu."""

import numpy as np


def variantes(avant, ouvert, actuel, action, modele):
    if not isinstance(action, list) or action[0] != "clic":
        raise ValueError("Clic requis")
    if modele.position(avant) != modele.position(ouvert) or modele.position(ouvert) != modele.position(actuel):
        raise ValueError("Position différente : expérience non couverte")
    mask = avant != ouvert
    mask[-1] = False
    ys, xs = np.nonzero(mask)
    if not len(xs) or len(xs) > 2 * modele.pas**2:
        raise ValueError("Ouverture non locale")
    if np.mean(ouvert[mask] == modele.sol) < 0.7 or not np.array_equal(actuel[mask], ouvert[mask]):
        raise ValueError("Ouverture non conservée")
    if max(xs) - min(xs) > modele.pas or max(ys) - min(ys) > modele.pas:
        raise ValueError("Effet dispersé")
    if (
        not min(xs) - modele.pas <= action[1] <= max(xs) + modele.pas
        or not min(ys) - modele.pas <= action[2] <= max(ys) + modele.pas
    ):
        raise ValueError("Clic hors zone")
    ferme = np.array(actuel, copy=True)
    ferme[mask] = avant[mask]
    return {"reste_ouvert": (np.array(actuel, copy=True), 0), "refermeture_locale": (ferme, 0)}
