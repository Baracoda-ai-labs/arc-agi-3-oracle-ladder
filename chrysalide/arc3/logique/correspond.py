# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — mots génériques pour passer d'un niveau à l'autre (CCM-025/027-C, CW-122 étape 4) :
- `dessin(pixels)` : dessin d'une zone, recadré sur sa partie non unie (cadre retiré), ramené à la plus petite échelle
  entière, couleurs renommées par ordre d'apparition (le dessin ne dépend pas des couleurs exactes) ;
- `correspond(a, b)` : deux zones portent le même dessin, à l'échelle près (clé portée = motif de la porte, ls20) ;
- `aliaser(th, monde)` : une classe statique INCONNUE hérite de la solidité des classes connues de même apparence
  (même couleur ou même motif de case), si elles sont unanimes — hypothèse nommée H_alias, révisable."""
from dataclasses import replace

import numpy as np


def _recadrer(p):
    """Retire les lignes et colonnes de bord unies (de la couleur du bord), tant qu'il en reste."""
    p = np.asarray(p)
    while p.shape[0] > 1 and p.shape[1] > 1:
        bord = p[0, 0]
        if (p[0] == bord).all() and (p[-1] == bord).all() and (p[:, 0] == bord).all() and (p[:, -1] == bord).all():
            p = p[1:-1, 1:-1]
        else:
            break
    return p


def _reduire(p):
    """Plus petite échelle entière : blocs k×k uniformes → un pixel."""
    h, w = p.shape
    for k in range(min(h, w), 1, -1):
        if h % k or w % k:
            continue
        b = p.reshape(h // k, k, w // k, k)
        if (b == b[:, :1, :, :1]).all():
            return b[:, 0, :, 0]
    return p


def dessin(pixels):
    p = _reduire(_recadrer(pixels))
    noms = {}
    return tuple(tuple(noms.setdefault(int(v), len(noms)) for v in ligne) for ligne in p)


def correspond(a, b):
    da, db = dessin(a), dessin(b)
    return da == db and len(da) > 1


def aliaser(th, monde, signature):
    """`signature(classe)` → apparence (couleur ou motif) ou None. Renvoie (théorie, alias ajoutés)."""
    connues = set(th.formes)
    par_sig = {}
    for c in connues:
        s = signature(c)
        if s is not None:
            par_sig.setdefault(s, []).append(c)
    ajout = set()
    for o in monde:
        u = o[0]
        if u in connues or u in ajout:
            continue
        semblables = par_sig.get(signature(u), [])
        if semblables and all(c in th.solides for c in semblables):
            ajout.add(u)
    return replace(th, solides=th.solides | ajout, murs_supposes=th.murs_supposes | ajout), ajout
