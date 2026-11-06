"""Rupture de masse chromatique exclusive au contrôle, sans statut ni couleur prescrite."""

import numpy as np
from issues_observees import scene_image


def apprendre(modele, contexte=()):
    exclusives = set(modele.palette)
    masses = []
    for g in [*modele.images, *contexte]:
        sc = scene_image(g, modele)
        actors = [o for o in sc.sprites if "controle" in o.get("tags", ())]
        if len(actors) != 1:
            raise ValueError("Référence contrôle ambiguë")
        a = actors[0]
        mask = np.zeros_like(g, dtype=bool)
        yy, xx = np.nonzero(a["pixels"] >= 0)
        mask[yy + a["y"], xx + a["x"]] = True
        exclusives -= set(map(int, g[:-1][~mask[:-1]].ravel()))
        masses.append(g)
    if not exclusives:
        return {"couleurs_exclusives": [], "masse_min": None}
    return {
        "couleurs_exclusives": sorted(exclusives),
        "masse_min": min(int(np.isin(g[:-1], list(exclusives)).sum()) for g in masses),
    }


def detecter(images, profil, persistance=2):
    if persistance < 1:
        raise ValueError("Persistance positive requise")
    colors, base = profil["couleurs_exclusives"], profil["masse_min"]
    if not colors or base is None or base <= 0:
        return {"statut": "non_observable", "debut": None, "masses": []}
    masses = [int(np.isin(g[:-1], colors).sum()) for g in images]
    debut = next(
        (
            i
            for i in range(1, len(masses) - persistance + 1)
            if masses[i - 1] >= base and all(v < base for v in masses[i : i + persistance])
        ),
        None,
    )
    return {
        "statut": "rupture_visuelle" if debut is not None else "aucune_rupture",
        "debut": debut,
        "masses": masses,
        "persistance": persistance,
        "sens": "diminution persistante de couleur exclusive, pas collision ni défaite certifiée",
    }
