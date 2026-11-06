"""Interventions locales non monotones, limitées aux supports effectivement observés."""

import copy
from collections import deque

import numpy as np
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer


class InterventionsSupports(InterventionsElargies):
    def __init__(self, image, local, candidats, offre, *, supports=(), contexte=None, camera_dy=0, **kwargs):
        super().__init__(image, local, candidats, offre, **kwargs)
        self.supports_actifs = {}
        self.refus_supports = []
        closed_image = np.array(image, copy=True)
        opened = set()
        for regle in supports:
            if regle["contexte"] != contexte:
                self.refus_supports.append("contexte_different")
                continue
            xy = np.asarray(regle["pixels_xy"], dtype=int).copy()
            xy[:, 1] += camera_dy
            xs, ys = xy[:, 0], xy[:, 1]
            if np.any(xs < 0) or np.any(xs >= image.shape[1]) or np.any(ys < 0) or np.any(ys >= image.shape[0] - 1):
                self.refus_supports.append("support_partiellement_hors_champ")
                continue
            values = image[ys, xs]
            is_open = np.array_equal(values, regle["ouvert"])
            if not is_open and not np.array_equal(values, regle["ferme"]):
                self.refus_supports.append("pixels_non_conformes")
                continue
            action = (regle["action"][0], regle["action"][1], regle["action"][2] + camera_dy)
            cell = ((action[1] - self.origin[0]) // self.m.pas, (action[2] - self.origin[1]) // self.m.pas)
            closed_test = np.array(image, copy=True)
            open_test = np.array(image, copy=True)
            closed_test[ys, xs] = regle["ferme"]
            open_test[ys, xs] = regle["ouvert"]
            closed_grid = self.m.lire(closed_test)[0]
            open_grid = self.m.lire(open_test)[0]
            cells = {tuple(map(int, p[::-1])) for p in np.argwhere(closed_grid != open_grid)}
            if cells != {cell} or not np.all(np.asarray(regle["ouvert"]) == self.m.sol):
                self.refus_supports.append("support_non_binaire_sur_grille")
                continue
            self.supports_actifs[cell] = {"action": action, "pixels_xy": xy, "ferme": regle["ferme"]}
            self.free.discard(cell)
            self.blocks.add(cell)
            closed_image[ys, xs] = regle["ferme"]
            if is_open:
                opened.add(cell)
        if self.supports_actifs:
            self.scene = decomposer(closed_image, self.m)[0]
            self.actor = next(o for o in self.scene.sprites if "controle" in o.get("tags", ()))
            self.depart = (self.start, frozenset(opened), self.depart[2], 0)
        self.cache_supports = {}

    def actions(self, s):
        if not self.supports_actifs:
            return super().actions(s)
        out = super().actions(s)
        # Un effet étayé à un pixel ne justifie pas un autre point de clic dans la cellule.
        normalized = []
        for action in out:
            if isinstance(action, tuple):
                cell = ((action[1] - self.origin[0]) // self.m.pas, (action[2] - self.origin[1]) // self.m.pas)
                action = self.supports_actifs.get(cell, {}).get("action", action)
            normalized.append(action)
        out = normalized
        if s[3] >= self.horizon or any(i != "continue" for i in s[2]) or not self.click or 6 not in self.offre:
            return out
        for cell, info in self.supports_actifs.items():
            if cell in s[1] and cell != s[0]:
                out.append(info["action"])
        return list(dict.fromkeys(out))

    def pas(self, s, a):
        if not self.supports_actifs:
            return super().pas(s, a)
        if a not in self.actions(s):
            return None
        before, removed, _issues, depth = s
        p = before
        if isinstance(a, tuple):
            cell = ((a[1] - self.origin[0]) // self.m.pas, (a[2] - self.origin[1]) // self.m.pas)
            removed = removed ^ {cell} if cell in self.supports_actifs else removed | {cell}
        else:
            p = (p[0] + (-1 if a == 3 else 1), p[1])
        while self.g and (p[0], p[1] + self.g) in self.free | set(removed):
            p = (p[0], p[1] + self.g)
        key = (before, p, removed)
        if key not in self.cache_supports:
            scene = copy.deepcopy(self.scene)
            actor = next(o for o in scene.sprites if "controle" in o.get("tags", ()))
            pixels_ouverts = {
                tuple(map(int, xy)) for cell, info in self.supports_actifs.items() if cell in removed for xy in info["pixels_xy"]
            }
            for obj in scene.sprites:
                if obj is actor:
                    continue
                for yy, xx in np.argwhere(obj["pixels"] >= 0):
                    cell = ((obj["x"] + xx - self.origin[0]) // self.m.pas, (obj["y"] + yy - self.origin[1]) // self.m.pas)
                    point = (int(obj["x"] + xx), int(obj["y"] + yy))
                    if (cell in removed and cell not in self.supports_actifs) or point in pixels_ouverts:
                        obj["pixels"][yy, xx] = -1
            actor["x"] += (before[0] - self.start[0]) * self.m.pas
            actor["y"] += (before[1] - self.start[1]) * self.m.pas
            found = dict.fromkeys(self.ids, "continue")
            # Même trajet pixel/natifs que la projection existante ; vérifier aussi un clic immobile.
            shifts = [(0, 0)]
            shifts += [(1 if p[0] > before[0] else -1, 0)] * abs((p[0] - before[0]) * self.m.pas)
            shifts += [(0, 1 if p[1] > before[1] else -1)] * abs((p[1] - before[1]) * self.m.pas)
            for dx, dy in shifts:
                actor["x"] += dx
                actor["y"] += dy
                for n, programme in self.programmes.items():
                    if found[n] != "continue":
                        continue
                    scene.issue = None
                    programme.step(scene, ("OBSERVE",))
                    found[n] = scene.issue or "continue"
            self.cache_supports[key] = tuple(found[n] for n in self.ids)
        return p, frozenset(removed), self.cache_supports[key], depth + 1


def chercher(model, horloge, temporel, max_noeuds=3000):
    """Explorer états et nouveaux arrêts ; l'horloge ne rembobine jamais avec la fermeture."""
    q = deque([(model.depart, [])])
    seen = {model.depart}
    records = []
    rejected = 0
    while q and len(seen) <= max_noeuds:
        s, path = q.popleft()
        for action in model.actions(s):
            t = model.pas(s, action)
            if t is None or any(v != "continue" for v in t[2]):
                continue
            bottom = (
                model.actor["y"] + model.actor["pixels"].shape[0] - 1 + (max(s[0][1], t[0][1]) - model.start[1]) * model.m.pas
            )
            margin = min(horloge.prevoir(temporel, t[3]), horloge.prevoir(temporel, s[3])) - bottom - 1
            if margin <= 0:
                rejected += 1
                continue
            if t in seen:
                continue
            seen.add(t)
            seq = path + [action]
            q.append((t, seq))
            records.append({"position": t[0], "ouverts": sorted(t[1]), "plan": seq, "marge": margin})
    return {
        "etats": len(seen),
        "tronque": bool(q),
        "rejets_temporels": rejected,
        "atteints": records,
        "supports_actifs": list(model.supports_actifs),
        "refus_supports": model.refus_supports,
    }
