"""Masques de compteurs candidats : priorité seulement, jamais identité du monde."""
import numpy as np
from chrysalide.arc3.masque import Masque


def cellules_priorite(images):
    cellules=set()
    # Un défilement ancien peut relier décor et jauge dans une grande composante.
    # Les mêmes critères de barre monotone restent applicables aux suffixes récents.
    for n in (len(images),5,9,17):
        m=Masque(court=True)
        extrait=images[-n:]
        for a,b in zip(extrait,extrait[1:]):m.observer(np.asarray(a).tolist(),np.asarray(b).tolist())
        cellules.update(m.cellules())
    return cellules
