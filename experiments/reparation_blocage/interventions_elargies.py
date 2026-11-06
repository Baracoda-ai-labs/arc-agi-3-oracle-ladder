"""Préparer des passages avec les seuls effets de clic déjà appris."""

import numpy as np
from experience_bfws import ExperienceLocale, techniques

from chrysalide.langue import depuis_python


def tags_ast(node):
    if isinstance(node, dict):
        return ({node["tag"]} if "tag" in node else set()) | set().union(*(tags_ast(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(tags_ast(v) for v in node))
    return set()


class InterventionsElargies(ExperienceLocale):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        candidats = args[2] if len(args) > 2 else kwargs["candidats"]
        tags = set().union(*(tags_ast(depuis_python(c["python"])) for c in candidats.values())) - {"controle"}
        self.affectables = set()
        for o in self.scene.sprites:
            if set(o.get("tags", ())) & tags:
                for yy, xx in np.argwhere(o["pixels"] >= 0):
                    self.affectables.add(
                        ((int(o["x"] + xx) - self.origin[0]) // self.m.pas, (int(o["y"] + yy) - self.origin[1]) // self.m.pas)
                    )
        self.predictions_cache = {}
        self.appels = 0

    def actions(self, s):
        if s[3] >= self.horizon or any(i != "continue" for i in s[2]):
            return []
        out = [a for a in super().actions(s) if not isinstance(a, tuple)]
        if self.click and 6 in self.offre:
            out += [
                (
                    "clic",
                    int(self.origin[0] + x * self.m.pas + self.m.pas // 2),
                    int(self.origin[1] + y * self.m.pas + self.m.pas // 2),
                )
                for x, y in sorted(self.blocks - set(s[1]))
            ]
        return out

    def pas(self, s, a):
        self.appels += 1
        if a not in self.actions(s):
            return None
        before, removed, _issues, depth = s
        p = before
        if isinstance(a, tuple):
            removed = removed | {((a[1] - self.origin[0]) // self.m.pas, (a[2] - self.origin[1]) // self.m.pas)}
        else:
            p = (p[0] + (-1 if a == 3 else 1), p[1])
        while self.g and (p[0], p[1] + self.g) in self.free | set(removed):
            p = (p[0], p[1] + self.g)
        key = (before, p, frozenset(removed & self.affectables))
        if key not in self.predictions_cache:
            result = super().pas(s, a)
            self.predictions_cache[key] = result[2]
        return p, removed, self.predictions_cache[key], depth + 1

    def chercher_minimal(self, interdits=(), max_noeuds=3000):
        def actions(s):
            return [
                a for a in self.actions(s) if s != self.depart or str(list(a) if isinstance(a, tuple) else a) not in interdits
            ]

        plan = techniques().bfs(self.depart, self.pas, actions, lambda s: len(set(s[2])) > 1, max_noeuds=max_noeuds)
        cur = self.depart
        steps = []
        if plan:
            for a in plan:
                cur = self.pas(cur, a)
                steps.append({"position": cur[0], "predictions": dict(zip(self.ids, cur[2], strict=True))})
        return {
            "plan": plan,
            "etapes": steps,
            "transitions_calculees": self.appels,
            "projections_distinctes": len(self.predictions_cache),
            "horizon": self.horizon,
            "max_noeuds": max_noeuds,
            "statut": "experience_separatrice_simulee" if plan else "aucune_dans_budget",
            "modele": "préparation de blocs cassables observés ; projection locale, caméra fixe",
            "source_recherche": "stratégies couche6 BFS ; coûts unitaires, minimum dans graphe exploré",
        }
