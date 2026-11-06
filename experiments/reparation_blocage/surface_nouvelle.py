"""Proposer un clic diagnostique sur une classe nouvelle latérale, jamais un effet certain."""

from experience_regles_bp35 import cle


def proposer(image, m, couleurs_connues, offre, known):
    if 6 not in offre:
        return None
    grid, p, origin = m.lire(image)
    for dx in (-1, 1):
        x, y = p[0] + dx, p[1]
        if not (0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]):
            continue
        color = int(grid[y, x])
        if color in couleurs_connues or color in m.cassables or color == m.sol:
            continue
        a = ["clic", int(origin[0] + x * m.pas + m.pas // 2), int(origin[1] + y * m.pas + m.pas // 2)]
        if cle(image, a) not in known:
            return {
                "plan": [a],
                "raison": "sonde_classe_visuelle_nouvelle",
                "couleur_observee": color,
                "hypothese": "un clic pourrait modifier cette surface latérale ; effet inconnu",
                "etapes": [{"predictions": {}}],
            }
    return None
