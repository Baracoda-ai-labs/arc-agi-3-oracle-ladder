"""Catalogue borné de dynamiques visibles, sélection par réfutation observable.
Les opérateurs sont fournis ; leur sélection n'est pas une invention de mécanique.
"""

import copy
from collections import Counter

import numpy as np
from atms import ATMS
from boucle_navigation_visible import decalage
from issues_observees import comparer_issue


class HypothesesNavigation:
    def __init__(self, modele, buts=(), clics=(False, True)):
        self.modele = modele
        self.buts = set(buts)
        self.atms = ATMS()
        self.catalogue = {f"g{g}_clic{int(c)}": (g, c) for g in (-1, 0, 1) for c in clics}
        for name in self.catalogue:
            self.atms.supposer(name)
        self.atms.supposer("couverture_issues")
        self.journal = []

    def actives(self):
        return [n for n in self.catalogue if self.atms.tient(n, [n])]

    def scene(self, image):
        m = self.modele
        grid, start, origin = m.lire(image)
        free = {tuple(map(int, p[::-1])) for p in np.argwhere(grid == m.sol)}
        blocks = {tuple(map(int, p[::-1])) for p in np.argwhere(np.isin(grid, list(m.cassables)))}
        goals = set()
        for y, x in np.argwhere(np.isin(image, list(self.buts))):
            cell = ((int(x) - origin[0]) // m.pas, (int(y) - origin[1]) // m.pas)
            if 0 <= cell[0] < grid.shape[1] and 0 <= cell[1] < grid.shape[0]:
                goals.add(cell)
        return start, origin, free | goals, blocks

    def predire(self, image, action, nom):
        start, origin, free, blocks = self.scene(image)
        g, c = self.catalogue[nom]
        p = start
        removed = None
        if isinstance(action, list):
            cell = ((action[1] - origin[0]) // self.modele.pas, (action[2] - origin[1]) // self.modele.pas)
            if c and cell in blocks:
                free.add(cell)
                removed = cell
        elif action in (3, 4):
            nxt = (p[0] + (-1 if action == 3 else 1), p[1])
            if nxt in free:
                p = nxt
        else:
            raise ValueError("Action hors catalogue")
        while g and (p[0], p[1] + g) in free:
            p = (p[0], p[1] + g)
        return {"position": p, "origine": origin, "retire": removed, "issue": "inconnue"}

    def observer(self, avant, action, apres, film, issue_observee="continue"):
        terminal = comparer_issue("inconnue", issue_observee)
        if issue_observee != "continue":
            self.atms.interdire(["couverture_issues"])
            record = {
                **terminal,
                "statut": "issue_non_modelisee",
                "plan_invalide": True,
                "frames": len(film),
                "actives": self.actives(),
                "comparaisons": [],
                "position_non_evaluee": "transition terminale",
                "portee": "issue SDK enregistrée ; gravité non réfutée par une cause inconnue",
            }
            self.journal.append(record)
            return record
        dy, err = decalage(avant, apres, self.modele.palette)
        pos = self.modele.position(apres)
        details = []
        if err > 0.15:
            raise ValueError("Défilement insuffisamment expliqué : aucune réfutation sûre")
        for nom in self.actives():
            p = self.predire(avant, action, nom)
            s = self.modele.pas
            ox, oy = p["origine"]
            x, y = p["position"]
            expected = (ox + x * s + s // 2, oy + y * s + s // 2 + dy)
            conforme = expected == pos
            clic = None
            if isinstance(action, list):
                cx, cy = action[1], action[2] + dy
                if s // 2 <= cx < 64 - s // 2 and s // 2 <= cy < 63 - s // 2:
                    patch = apres[cy - s // 2 : cy + s // 2, cx - s // 2 : cx + s // 2]
                    # Ne pas attribuer une disparition quand le joueur occupe la case.
                    if not np.isin(patch, list(self.modele.palette)).any():
                        actual_free = Counter(patch.ravel().tolist()).most_common(1)[0][0] == self.modele.sol
                        _, origin, _, blocks = self.scene(avant)
                        cell = ((action[1] - origin[0]) // s, (action[2] - origin[1]) // s)
                        if cell in blocks:
                            clic = actual_free == (p["retire"] is not None)
                            conforme &= clic
            details.append({"hypothese": nom, "position_predite": expected, "conforme": bool(conforme), "clic_conforme": clic})
            if not conforme:
                self.atms.interdire([nom])
        record = {
            **terminal,
            "decalage_y": dy,
            "erreur_decor": err,
            "position_observee": pos,
            "comparaisons": details,
            "frames": len(film),
            "actives": self.actives(),
            "portee": "position et disparition locale ; pas modèle pixel complet",
        }
        self.journal.append(record)
        return record

    def proposer(self, image, offre):
        active = self.actives()
        if not active:
            raise ValueError("Catalogue réfuté : extension nécessaire")
        plans = []
        actions = []
        for nom in active:
            g, c = self.catalogue[nom]
            m = copy.copy(self.modele)
            if not c:
                m.cassables = set()
            try:
                p = m.proposer(image, gravite=g, buts_connus=self.buts)
            except ValueError:
                continue
            code = 6 if isinstance(p["action"], list) else p["action"]
            if code in offre:
                plans.append((nom, p))
                actions.append(p["action"])
        # Les expériences possibles viennent des actions offertes et des objets perçus.
        start, origin, _free, blocks = self.scene(image)
        actions.extend(a for a in (3, 4) if a in offre)
        if 6 in offre:
            actions.extend(
                [
                    "clic",
                    int(origin[0] + x * self.modele.pas + self.modele.pas // 2),
                    int(origin[1] + y * self.modele.pas + self.modele.pas // 2),
                ]
                for x, y in sorted(blocks)
            )
        unique = {str(a): a for a in actions}
        scores = []
        for action in unique.values():
            predictions = {nom: self.predire(image, action, nom) for nom in active}
            groups = Counter((tuple(p["position"]), p["retire"]) for p in predictions.values())
            # Minimax sur le nombre d'hypothèses restant après l'observation.
            gain = len(active) - max(groups.values())
            support = [(n, p) for n, p in plans if p["action"] == action]
            progression = (
                max(
                    (
                        int(p["destination"] in p["buts_hypothetiques"]),
                        abs(p["destination"][1] - p["position"][1]),
                        -len(p["plan_local"]),
                    )
                    for n, p in support
                )
                if support
                else (-1, -1, -100)
            )
            effect = any(tuple(p["position"]) != start or p["retire"] is not None for p in predictions.values())
            if effect:
                scores.append(((gain, *progression), action, predictions, support))
        if not scores:
            raise ValueError("Aucune expérience ou progression prévue")
        score, action, predictions, support = max(scores, key=lambda item: item[0])
        return {
            "action": action,
            "raison": "experience_discriminante" if score[0] > 0 else "plan_conditionnel",
            "hypotheses": active,
            "predictions": predictions,
            "gain_minimax": score[0],
            "plans_supports": [{"hypothese": n, **p} for n, p in support],
            "experiences_candidates": [
                {"action": a, "gain_minimax": sc[0], "predictions": pr}
                for sc, a, pr, su in sorted(scores, key=lambda item: item[0], reverse=True)[:12]
            ],
        }
