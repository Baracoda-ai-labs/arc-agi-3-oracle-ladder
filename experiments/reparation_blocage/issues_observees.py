"""Issues du langage existant et scènes perceptives, sans accès au moteur du jeu."""

import numpy as np

from chrysalide.arc3.films import composantes
from chrysalide.arc3.ontologie_exec import Scene


def issue_sdk(state, niveaux, baseline):
    if "GAME_OVER" in str(state):
        return "defaite"
    if "WIN" in str(state):
        return "victoire"
    if niveaux > baseline:
        return "niveau"
    return "continue"


def comparer_issue(predite, observee):
    if predite not in ("inconnue", "continue", "niveau", "victoire", "defaite"):
        raise ValueError("Issue prédite invalide")
    if observee not in ("continue", "niveau", "victoire", "defaite"):
        raise ValueError("Issue observée invalide")
    return {
        "issue_predite": predite,
        "issue_observee": observee,
        "issue_conforme": None if predite == "inconnue" else predite == observee,
        "couverture_issue": predite != "inconnue",
    }


def scene_image(image, modele):
    """Masques visibles disjoints : un contact occulté peut rester inobservable."""
    from perception_navigation import candidats

    player = np.zeros_like(image, dtype=bool)
    centers = candidats(modele, image)
    if len(centers) == 1:
        x, y = centers[0]
        for comp in composantes(np.isin(image, list(modele.palette))):
            xs = [p[0] for p in comp]
            ys = [p[1] for p in comp]
            if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                for a, b in comp:
                    player[b, a] = True
    sprites = []

    def add(comp, tag, color):
        xs = [p[0] for p in comp]
        ys = [p[1] for p in comp]
        patch = np.full((max(ys) - min(ys) + 1, max(xs) - min(xs) + 1), -1, dtype=int)
        for x, y in comp:
            patch[y - min(ys), x - min(xs)] = int(image[y, x])
        sprites.append(
            {
                "nom": f"objet_{len(sprites)}",
                "x": min(xs),
                "y": min(ys),
                "pixels": patch,
                "tags": [tag],
                "couleur": color,
                "couche": 0,
                "bloquant": True,
                "attrs": {},
            }
        )

    if player.any():
        add([(int(x), int(y)) for y, x in np.argwhere(player)], "controle", None)
    for c in np.unique(image):
        mask = (image == c) & ~player
        mask[-1] = False
        for comp in composantes(mask):
            add(comp, f"couleur_{int(c)}", int(c))
    return Scene((64, 64), modele.sol, 0, sprites)
