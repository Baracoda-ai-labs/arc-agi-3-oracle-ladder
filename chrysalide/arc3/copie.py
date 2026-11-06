# SPDX-License-Identifier: MIT-0
"""Copie profonde d'un jeu du moteur, FERMETURES COMPRISES. `copy.deepcopy` partage les fonctions : une lambda qui capture
`self` (tn36 : table d'actions) ferait agir la copie sur l'ORIGINAL (trouvé par le banc des distracteurs, 18/10)."""
import copy
import types


def _copier_fonction(f, memo):
    if not f.__closure__:
        return f
    cellules = tuple(types.CellType() for _ in f.__closure__)
    g = types.FunctionType(f.__code__, f.__globals__, f.__name__, f.__defaults__, cellules)
    g.__kwdefaults__, g.__dict__ = f.__kwdefaults__, dict(f.__dict__)
    memo[id(f)] = g  # avant de copier les cellules : un cycle (self → table → lambda → self) retombe sur g
    for c, n in zip(f.__closure__, cellules, strict=True):
        try:
            contenu = c.cell_contents
        except ValueError:  # cellule vide
            continue
        n.cell_contents = copy.deepcopy(contenu, memo)
    return g


def copie_profonde(obj, memo=None):
    d = copy._deepcopy_dispatch
    ancien = d.get(types.FunctionType)
    d[types.FunctionType] = _copier_fonction
    try:
        return copy.deepcopy(obj, memo)
    finally:
        d[types.FunctionType] = ancien
