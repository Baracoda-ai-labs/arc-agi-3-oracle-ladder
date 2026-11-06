"""Motifs de grille candidats avec parties exactes ; aucune couleur de jeu prescrite."""

import hashlib

import numpy as np
from issues_observees import scene_image

from chrysalide.arc3.films import composantes
from chrysalide.arc3.ontologie_exec import Scene


def objet(image, points, tags, nom, attrs=None):
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    mask = np.full((max(ys) - min(ys) + 1, max(xs) - min(xs) + 1), -1, dtype=int)
    for x, y in points:
        mask[y - min(ys), x - min(xs)] = image[y, x]
    return {
        "x": min(xs),
        "y": min(ys),
        "pixels": mask,
        "tags": tags,
        "nom": nom,
        "bloquant": True,
        "couche": 0,
        "attrs": attrs or {},
    }


def decomposer(image, modele, origine=None):
    base = scene_image(image, modele)
    if origine is None:
        _, _, origine = modele.lire(image)
    fonds = {
        int(modele.sol),
        int(np.bincount(np.asarray(getattr(modele, "images", [image])[0][:-1], dtype=int).ravel()).argmax()),
    }
    controle = np.zeros_like(image, dtype=bool)
    actors = [o for o in base.sprites if "controle" in o.get("tags", ())]
    for a in actors:
        yy, xx = np.nonzero(a["pixels"] >= 0)
        controle[yy + a["y"], xx + a["x"]] = True
    parents = []
    parts = []
    s = modele.pas
    ox, oy = origine
    for top in range(oy % s - s, 63, s):
        for left in range(ox % s - s, 64, s):
            y0, y1 = max(0, top), min(63, top + s)
            x0, x1 = max(0, left), min(64, left + s)
            if y1 <= y0 or x1 <= x0:
                continue
            area = image[y0:y1, x0:x1]
            foreground = ~np.isin(area, list(fonds)) & ~controle[y0:y1, x0:x1]
            for comp in composantes(foreground):
                points = {(x + x0, y + y0) for x, y in comp}
                parent = objet(image, points, [], f"parent_{len(parents)}")
                signature = hashlib.sha256(
                    np.asarray(parent["pixels"], dtype=np.int16).tobytes() + str(parent["pixels"].shape).encode()
                ).hexdigest()[:12]
                parent["tags"] = ["motif_" + signature]
                parent["attrs"] = {"type_candidat": signature, "cellule": [left, top], "fond_exclus": sorted(fonds)}
                parents.append(parent)
                for color in sorted({int(image[y, x]) for x, y in points}):
                    selected = {(x, y) for x, y in points if int(image[y, x]) == color}
                    part = objet(image, selected, [f"couleur_{color}"], f"partie_{len(parts)}", {"parent": parent["nom"]})
                    parts.append(part)
    backgrounds = [o for o in base.sprites if o.get("couleur") in fonds]
    # Le parent est un concept séparé ; pas de double sprite dans les collisions.
    scene = Scene((64, 64), modele.sol, 0, [*backgrounds, *parts, *actors])
    return scene, parents


def points_opaques(o):
    yy, xx = np.nonzero(np.asarray(o["pixels"]) >= 0)
    return np.column_stack((xx + o["x"], yy + o["y"]))


def contact_observe(a, b):
    aa, bb = points_opaques(a), points_opaques(b)
    if not len(aa) or not len(bb):
        return {"distance_pixels": None, "contact": "inconnu"}
    # Distance des pixels visibles, distincte de la boîte englobante et du volume caché.
    d = np.max(np.abs(aa[:, None, :] - bb[None, :, :]), axis=2)
    i, j = np.unravel_index(np.argmin(d), d.shape)
    return {
        "distance_pixels": int(d[i, j]),
        "pixels_proches": [aa[i].tolist(), bb[j].tolist()],
        "contact": "recouvrement_visible" if d[i, j] == 0 else "sans_recouvrement_visible",
        "collision_cachee": "inconnue",
    }
