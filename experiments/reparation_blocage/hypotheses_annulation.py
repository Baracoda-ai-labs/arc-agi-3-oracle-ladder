"""Prédictions concurrentes d'annulation, sans présumer leur exhaustivité."""

from itertools import pairwise

import numpy as np
from boucle_navigation_visible import decalage


def variantes(images, actions, modele):
    if not actions or not any(isinstance(a, list) for a in actions):
        raise ValueError("Pas de clic antérieur pour une hypothèse de restauration")
    cameras = [0]
    for before, after in pairwise(images):
        dy, err = decalage(before, after, modele.palette)
        if err > 0.15:
            raise ValueError("Caméra non couverte")
        cameras.append(cameras[-1] + dy)
    clic = max(i for i, a in enumerate(actions) if isinstance(a, list))
    before, after = images[clic : clic + 2]
    if cameras[clic] != cameras[clic + 1]:
        raise ValueError("Modification terrain avec caméra : variante non couverte")
    restored = np.array(images[-1], copy=True)
    ys, xs = np.nonzero(before[:-1] != after[:-1])
    dy = cameras[-1] - cameras[clic]
    for y, x in zip(ys, xs):
        if 0 <= y + dy < restored.shape[0] - 1:
            restored[y + dy, x] = before[y, x]
    return {
        "inerte": (np.array(images[-1], copy=True), cameras[-1]),
        "etat_avant_derniere_action": (np.array(images[-2], copy=True), cameras[-2]),
        "etat_avant_dernier_clic": (np.array(before, copy=True), cameras[clic]),
        "terrain_seul_dernier_clic": (restored, cameras[-1]),
    }


def comparer(image, predictions):
    diffs = {n: int(np.sum(image[:-1] != im[:-1])) for n, (im, _camera) in predictions.items()}
    compatibles = [n for n, nb in diffs.items() if nb == 0]
    return {
        "ecarts_pixels_hors_hud": diffs,
        "compatibles": compatibles,
        "statut": "hors_catalogue" if not compatibles else "compatible_localement",
        "portee": "comparaison de prédictions visuelles, pas preuve de mécanisme global ou de phase restaurée",
    }
