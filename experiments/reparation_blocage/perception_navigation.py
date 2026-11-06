"""Hypothèse alternative : motif connexe observé, plutôt qu'union des couleurs."""

import math

import numpy as np

from chrysalide.arc3.films import composantes


def motifs(modele):
    templates = set()
    for g in modele.images:
        mask = np.isin(g, list(modele.palette))
        ys, xs = np.nonzero(mask)
        patch = np.where(mask, g, -1)[min(ys) : max(ys) + 1, min(xs) : max(xs) + 1]
        templates.add(tuple(map(tuple, patch)))
        templates.add(tuple(map(tuple, patch[:, ::-1])))
    return templates


def candidats(modele, g):
    templates = motifs(modele)
    out = []
    for comp in composantes(np.isin(g, list(modele.palette))):
        xs = [p[0] for p in comp]
        ys = [p[1] for p in comp]
        patch = np.full((max(ys) - min(ys) + 1, max(xs) - min(xs) + 1), -1)
        for x, y in comp:
            patch[y - min(ys), x - min(xs)] = g[y, x]
        if tuple(map(tuple, patch)) in templates:
            out.append((math.ceil((min(xs) + max(xs)) / 2), math.ceil((min(ys) + max(ys)) / 2)))
    return out


def position(modele, g):
    found = candidats(modele, g)
    if len(found) != 1:
        raise ValueError(f"Motif connexe non unique : {len(found)} candidats")
    return found[0]
