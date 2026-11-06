"""Appariement temporel conservateur de motifs dupliqués, sans but ni identité de jeu.

Le pisteur fournit les objets candidats ; cette couche vérifie une affectation
bijective de coût spatial minimal unique. Ce prior de continuité est une hypothèse,
pas une preuve d'identité causale. Ambiguïté, disparition et occultation sont refusées.
"""
from itertools import permutations
import numpy as np


def occurrences(g, motif):
    h, w = motif.shape
    fen = np.lib.stride_tricks.sliding_window_view(np.asarray(g), (h, w))
    masque = motif >= 0
    ys, xs = np.nonzero((fen[..., masque] == motif[masque]).all(axis=-1))
    return sorted(zip(xs.tolist(), ys.tolist()))


def suivre_motif(images, motif, cardinalite):
    if not 2 <= cardinalite <= 6:
        raise ValueError('Cardinalité identités hors domaine borné')
    series = []
    precedent = None
    for image in images:
        candidats = occurrences(image, motif)
        if len(candidats) != cardinalite:
            raise ValueError('Identités inconnues : disparition, occultation ou multiplicité changée')
        if precedent is None:
            courant = tuple(candidats)
        else:
            couts = []
            for affectation in permutations(candidats):
                cout = sum((x-a)**2 + (y-b)**2 for (a,b),(x,y) in zip(precedent, affectation))
                couts.append((cout, affectation))
            couts.sort()
            if couts[0][0] == couts[1][0]:
                raise ValueError('Identités ambiguës : affectations de coût égal')
            courant = couts[0][1]
        # Deux motifs ne peuvent partager des pixels visibles : sinon identité inconnue.
        occupation = set()
        ys, xs = np.nonzero(motif >= 0)
        for x,y in courant:
            cases = {(x+int(xx), y+int(yy)) for yy,xx in zip(ys,xs)}
            if occupation & cases:
                raise ValueError('Identités inconnues : motifs superposés')
            occupation |= cases
        series.append(courant)
        precedent = courant
    # Un même état visuel doit conserver le même étiquetage, sinon le modèle requiert une mémoire supplémentaire.
    connus = {}
    for image, positions in zip(images, series):
        cle = np.asarray(image).tobytes()
        if cle in connus and connus[cle] != positions:
            raise ValueError('Identités inconnues : même image avec étiquetages incompatibles')
        connus[cle] = positions
    return series
