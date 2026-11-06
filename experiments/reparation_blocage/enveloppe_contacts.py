"""Sur-approximation des arrêts sur grille ; jamais une séquence SDK."""

import copy
from collections import deque


def analyser(model):
    if model.blocks & model.affectables:
        return {"statut": "non_applicable", "raison": "retraits peuvent changer les objets visés"}
    allowed = model.free | model.blocks
    cache = {}

    def issues(before, end):
        key = (before, end)
        if key in cache:
            return cache[key]
        sc = copy.deepcopy(model.scene)
        actor = next(o for o in sc.sprites if "controle" in o.get("tags", ()))
        actor["x"] += (before[0] - model.start[0]) * model.m.pas
        actor["y"] += (before[1] - model.start[1]) * model.m.pas
        found = dict.fromkeys(model.ids, "continue")
        for axis, delta in (("x", (end[0] - before[0]) * model.m.pas), ("y", (end[1] - before[1]) * model.m.pas)):
            for _ in range(abs(delta)):
                actor[axis] += 1 if delta > 0 else -1
                for n, program in model.programmes.items():
                    if found[n] != "continue":
                        continue
                    sc.issue = None
                    program.step(sc, ("OBSERVE",))
                    found[n] = sc.issue or "continue"
        cache[key] = tuple(found[n] for n in model.ids)
        return cache[key]

    queue = deque([model.start])
    seen = {model.start}
    edges = []
    separators = []
    while queue:
        p = queue.popleft()
        starts = [p] + [(p[0] + dx, p[1]) for dx in (-1, 1) if (p[0] + dx, p[1]) in allowed]
        for q in starts:
            end = q
            while end in allowed:
                result = issues(p, end)
                row = {"depart": p, "arrivee": end, "issues": dict(zip(model.ids, result, strict=True))}
                edges.append(row)
                if len(set(result)) > 1:
                    separators.append(row)
                if all(x == "continue" for x in result) and end not in seen:
                    seen.add(end)
                    queue.append(end)
                if not model.g:
                    break
                end = (end[0], end[1] + model.g)
    return {
        "statut": "separation_dans_enveloppe" if separators else "aucune_separation_dans_enveloppe",
        "positions": len(seen),
        "transitions": len(edges),
        "separateurs": separators,
        "aretes": edges,
        "portee": "sur-approximation du modèle fixe : tout bloc franchissable, arrêt sur toute cellule autorisé ; pas jeu réel",
    }
