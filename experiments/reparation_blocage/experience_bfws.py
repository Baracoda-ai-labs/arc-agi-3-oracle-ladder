"""Recherche d'une expérience séparatrice avec le BFWS existant, modèle local explicite."""

import copy
import importlib.util
from pathlib import Path

import numpy as np
from issues_observees import scene_image

from chrysalide.arc3.langage import Programme
from chrysalide.langue import depuis_python


def techniques():
    path = Path(__file__).resolve().parents[1] / "defi_llm/couche6/strategies/techniques.py"
    spec = importlib.util.spec_from_file_location("_techniques_reutilisees", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ExperienceLocale:
    def __init__(self, image, local, candidats, offre, horizon=4, scene_factory=None):
        if len(local.actives()) != 1:
            raise ValueError("Dynamique locale non départagée")
        self.m = local.modele
        self.start, self.origin, self.free, self.blocks = local.scene(image)
        self.g, self.click = local.catalogue[local.actives()[0]]
        self.scene = (scene_factory or scene_image)(image, self.m)
        self.actor = next(o for o in self.scene.sprites if "controle" in o.get("tags", ()))
        self.x, self.y = self.m.position(image)
        self.programmes = {n: Programme(depuis_python(c["python"])) for n, c in candidats.items()}
        self.ids = list(candidats)
        self.offre = offre
        self.horizon = horizon
        self.cache = {}
        self.depart = (self.start, frozenset(), tuple("continue" for _ in candidats), 0)

    def actions(self, s):
        p, removed, issues, depth = s
        if depth >= self.horizon or any(i != "continue" for i in issues):
            return []
        actions = []
        for a, dx in ((3, -1), (4, 1)):
            if a in self.offre and (p[0] + dx, p[1]) in self.free | set(removed):
                actions.append(a)
        if self.click and 6 in self.offre:
            # Interventions sur le voisinage du contrôle, pas décor distant sans lien prédit.
            for x, y in sorted(self.blocks - set(removed)):
                if abs(x - p[0]) + abs(y - p[1]) == 1:
                    actions.append(
                        (
                            "clic",
                            int(self.origin[0] + x * self.m.pas + self.m.pas // 2),
                            int(self.origin[1] + y * self.m.pas + self.m.pas // 2),
                        )
                    )
        return actions

    def pas(self, s, a):
        p, removed, _issues, depth = s
        if a not in self.actions(s):
            return None
        before = p
        if isinstance(a, tuple):
            cell = ((a[1] - self.origin[0]) // self.m.pas, (a[2] - self.origin[1]) // self.m.pas)
            removed = removed | {cell}
        else:
            p = (p[0] + (-1 if a == 3 else 1), p[1])
        while self.g and (p[0], p[1] + self.g) in self.free | set(removed):
            p = (p[0], p[1] + self.g)
        key = (before, p, removed)
        if key not in self.cache:
            scene = copy.deepcopy(self.scene)
            actor = next(o for o in scene.sprites if "controle" in o.get("tags", ()))
            for o in scene.sprites:
                if o is actor:
                    continue
                for yy, xx in np.argwhere(o["pixels"] >= 0):
                    cell = ((o["x"] + xx - self.origin[0]) // self.m.pas, (o["y"] + yy - self.origin[1]) // self.m.pas)
                    if cell in removed:
                        o["pixels"][yy, xx] = -1
            actor["x"] += (before[0] - self.start[0]) * self.m.pas
            actor["y"] += (before[1] - self.start[1]) * self.m.pas
            found = dict.fromkeys(self.ids, "continue")
            for axis, delta in (("x", (p[0] - before[0]) * self.m.pas), ("y", (p[1] - before[1]) * self.m.pas)):
                for _ in range(abs(delta)):
                    actor[axis] += 1 if delta > 0 else -1
                    for n, program in self.programmes.items():
                        if found[n] != "continue":
                            continue
                        scene.issue = None
                        program.step(scene, ("OBSERVE",))
                        found[n] = scene.issue or "continue"
            self.cache[key] = tuple(found[n] for n in self.ids)
        return (p, removed, self.cache[key], depth + 1)

    def chercher(self, interdits=(), max_noeuds=500):
        def actions(s):
            return [
                a for a in self.actions(s) if s != self.depart or str(list(a) if isinstance(a, tuple) else a) not in interdits
            ]

        def atteint(s):
            return len(set(s[2])) > 1

        plan = techniques().bfws(
            self.depart,
            self.pas,
            actions,
            atteint,
            max_noeuds=max_noeuds,
            atomes=lambda s: {("pos", s[0]), *(("retire", x) for x in s[1]), *(("issue", i, v) for i, v in enumerate(s[2]))},
        )
        states = []
        cur = self.depart
        if plan:
            for a in plan:
                cur = self.pas(cur, a)
                states.append({"position": cur[0], "predictions": dict(zip(self.ids, cur[2], strict=True))})
        return {
            "plan": plan,
            "etapes": states,
            "transitions_calculees": len(self.cache),
            "modele": "projection locale partielle, caméra fixe, silhouettes conservées",
            "statut": "experience_separatrice_simulee" if plan else "aucune_dans_budget",
            "source_recherche": "experiments/defi_llm/couche6/strategies/techniques.py:bfws",
        }
