"""Recherche locale dans (positions, blocs retirés, phase, front), hypothèses explicites."""

from collections import deque
from types import SimpleNamespace

from experience_regles_bp35 import cle
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer


class HorlogeArchive:
    def __init__(self, journal):
        last = journal[-1]
        phases = [m for m in last["modeles"] if m["type"] == "phase_2"]
        if len(phases) != 1 or len(last["modeles"]) != 1:
            raise ValueError("Horloge non départagée")
        self.deltas = phases[0]["deltas"]
        self.rang = last["rang"]
        self.haut = last["front"]["haut"]
        self.decalage_camera = 0

    def bord(self, rang):
        if rang >= self.rang:
            return self.haut + sum(self.deltas[str(i % 2)] for i in range(self.rang + 1, rang + 1))
        return self.haut - sum(self.deltas[str(i % 2)] for i in range(rang + 1, self.rang + 1))

    def prevoir(self, temporel, depth):
        if temporel.etat is not None:
            return temporel.etat.haut + sum(self.deltas[str(i % 2)] for i in range(temporel.rang + 1, temporel.rang + depth + 1))
        return self.bord(temporel.rang + depth) + self.decalage_camera


def decision(image, h, cs, known, remaining, offre, garde, temporel, horloge, couleurs_connues, sondes):
    if not h.actives() or not cs or temporel.front_perdu:
        return {"plan": None, "raison": "couverture_absente"}
    models = []
    for name in h.actives():
        local = SimpleNamespace(modele=h.modele, catalogue=h.catalogue, actives=lambda n=name: [n], scene=h.scene)
        models.append(
            InterventionsElargies(
                image, local, cs, offre, horizon=min(10, remaining), scene_factory=lambda im, m: decomposer(im, m)[0]
            )
        )
    grid, _, origin = h.modele.lire(image)
    step = h.modele.pas
    initial = tuple(m.depart for m in models)
    q = deque([(initial, [], [])])
    seen = {initial}
    nodes = 0
    rejected = 0
    best = None

    def marge(states, previous, depth):
        # Bande pleine sous le front : sur-approximation des pixels pointillés.
        bottom = max(
            m.actor["y"] + m.actor["pixels"].shape[0] - 1 + (max(s[0][1], b[0][1]) - m.start[1]) * step
            for m, s, b in zip(models, states, previous)
        )
        return min(horloge.prevoir(temporel, depth), horloge.prevoir(temporel, max(0, depth - 1))) - bottom - 1

    def resultat(path, steps, reason, margin):
        return {
            "plan": path,
            "etapes": steps,
            "raison": reason,
            "marge_pixels": margin,
            "noeuds": nodes,
            "rejets_temporels": rejected,
            "portee": "route locale conditionnelle, bande conservative, horaire avant apparition extrapolé ; pas victoire prédite",
        }

    while q and nodes < 1200:
        states, path, checks = q.popleft()
        nodes += 1
        depth = len(path)
        positions = {s[0] for s in states}
        if depth and (len(positions) > 1 or all(m.g * (s[0][1] - m.start[1]) > 0 for m, s in zip(models, states))):
            score = (len(positions) > 1, min(m.g * (s[0][1] - m.start[1]) for m, s in zip(models, states)), -depth)
            if best is None or score > best[0]:
                best = (score, resultat(path, checks, "route_phase", checks[-1]["marge_pixels"]))
        if depth >= min(10, remaining):
            continue
        if len(positions) == 1 and 6 in offre:
            x, y = next(iter(positions))
            for dx in (-1, 1):
                xx = x + dx
                if not (0 <= y < grid.shape[0] and 0 <= xx < grid.shape[1]):
                    continue
                color = int(grid[y, xx])
                a = ["clic", int(origin[0] + xx * step + step // 2), int(origin[1] + y * step + step // 2)]
                if color in couleurs_connues or color in h.modele.cassables or color == h.modele.sol or (xx, y, color) in sondes:
                    continue
                if not path and cle(image, a) in known:
                    continue
                margin = marge(states, states, depth + 1)
                if margin <= 2 * max(abs(v) for v in horloge.deltas.values()):
                    continue
                # Effet du clic inconnu : aucune ouverture intégrée à la route.
                return resultat(
                    path + [a],
                    checks + [{"predictions": dict.fromkeys(cs, "inconnue"), "marge_pixels": margin, "surface": (xx, y, color)}],
                    "sonde_classe_visuelle_nouvelle" if not path else "route_vers_surface_inconnue",
                    margin,
                )
        common = set(models[0].actions(states[0]))
        for m, s in zip(models[1:], states[1:]):
            common &= set(m.actions(s))
        for a in sorted(common, key=str):
            normal = list(a) if isinstance(a, tuple) else a
            if not path and cle(image, normal) in known:
                continue
            nxt = tuple(m.pas(s, a) for m, s in zip(models, states))
            if any(s is None or any(v != "continue" for v in s[2]) for s in nxt):
                continue
            margin = marge(nxt, states, depth + 1)
            if margin <= 0:
                rejected += 1
                continue
            if nxt in seen:
                continue
            seen.add(nxt)
            q.append(
                (
                    nxt,
                    path + [normal],
                    checks
                    + [{"predictions": dict.fromkeys(cs, "continue"), "marge_pixels": margin, "positions": [s[0] for s in nxt]}],
                )
            )
    return best[1] if best else {"plan": None, "raison": "aucune_route_phase", "noeuds": nodes, "rejets_temporels": rejected}
