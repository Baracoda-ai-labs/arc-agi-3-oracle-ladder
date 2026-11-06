"""Clics sans effet visible : preuves causales, jamais suppression de transitions."""

import numpy as np
from classification_prefixe import information_film
from jauges_observees import jauges_validees


def preuve(images, actions, films, k):
    if films is None or len(films) != len(actions):
        raise ValueError("Films requis pour qualifier un clic négatif")
    film = np.asarray(films[k])
    if not len(film) or not np.array_equal(film[-1], images[k + 1]):
        raise ValueError("Film non aligné pour clic négatif")
    masque, rapports = jauges_validees(images[: k + 1], actions[:k])
    provenance = (
        {
            "origine": "jauges_validees",
            "coups_prefixe": k,
            "validations": rapports,
            "portee": "masque conditionnel de coût, pas absence d’effet caché",
        }
        if masque
        else None
    )
    info = information_film(images[k], film, sorted(masque), provenance)
    return {"coup": k + 1, "action": actions[k], **info, "cout_conserve": True, "effets_non_visuels": "inconnus"}


def normaliser(images, actions, films):
    normalise = list(actions)
    preuves = []
    for k, a in enumerate(actions):
        if not isinstance(a, list):
            continue
        p = preuve(images, actions, films, k)
        if not p["inerte"]:
            raise ValueError(f"Clic {k + 1} à effet visible non couvert par déplacement seul")
        normalise[k] = 6
        preuves.append(p)
    return normalise, preuves
