"""Recherche bornée : clics proposés sur les objets de chaque état simulé."""

import copy
import heapq
import itertools
import time

from chrysalide.arc3.logique.plan_langage import cle_complete
from chrysalide.arc3.sim_rapide import cloner


def actions_selection(scene, vue):
    actions = [("UP",), ("DOWN",), ("LEFT",), ("RIGHT",)]
    for piece in scene.sprites:
        if "piece" not in piece.get("tags", []):
            continue
        attrs = piece.get("attrs", {})
        mx = attrs.get("marqueur_x", vue.mx)
        my = attrs.get("marqueur_y", vue.my)
        if piece["pixels"][my, mx] == vue.selection:
            continue
        # Le point reste dans le marqueur observé de cette instance.
        cx = mx + attrs.get("marqueur_largeur", 1) // 2
        cy = my + attrs.get("marqueur_hauteur", 1) // 2
        actions.append(("MOUSE", piece["y"] + cy, piece["x"] + cx))
    return actions


def chercher(chaine, vue, secondes=15, max_noeuds=40000, max_profondeur=None, poids_heuristique=1, arreter=None):
    controle, courant = chaine.rejouer()
    if courant is None:
        return None, {"refus": controle}
    pc, initial = courant
    debut = time.monotonic()
    compteur = itertools.count()
    noeuds = 0

    def score(sc):
        ps = [s for s in sc.sprites if "piece" in s.get("tags", [])]
        ts = [s for s in sc.sprites if "cible" in s.get("tags", [])]
        total = 0
        for t in ts:
            candidats = [p for p in ps if not getattr(vue, "cibles_meme_forme", False)
                         or p["pixels"].shape == t["pixels"].shape]
            if not candidats:
                return float("inf")
            total += min(abs(p["x"] - t["x"]) + abs(p["y"] - t["y"]) for p in candidats)
        return total / max(vue.coque.shape)

    q = [(score(initial), next(compteur), initial, copy.deepcopy(pc.etat), [])]
    vus = {}
    while q and time.monotonic() - debut < secondes and noeuds < max_noeuds:
        if arreter is not None and arreter():
            return None, {"noeuds":noeuds,"secondes":time.monotonic()-debut,"refus":"annulation"}
        _, _, sc, etat, plan = heapq.heappop(q)
        cle = cle_complete(sc, etat)
        if cle in vus and vus[cle] <= len(plan):
            continue
        vus[cle] = len(plan)
        noeuds += 1
        if sc.issue in ("niveau", "victoire"):
            valide, preuve = chaine.verifier_plan(plan)
            return (plan if valide else None), {
                "noeuds": noeuds,
                "secondes": time.monotonic() - debut,
                "preuve": preuve,
                "valide": valide,
            }
        if max_profondeur is not None and len(plan) >= max_profondeur:
            continue
        acts = actions_selection(sc, vue)
        for a in acts:
            suivant, pc.etat = cloner(sc, etat)
            pc.step(suivant, a)
            if cle_complete(suivant, pc.etat) == cle:
                continue
            heapq.heappush(q, (len(plan) + 1 + poids_heuristique * score(suivant), next(compteur), suivant, copy.deepcopy(pc.etat), plan + [a]))
    return None, {"noeuds": noeuds, "secondes": time.monotonic() - debut, "refus": "budget" if q else "espace_epuise"}
