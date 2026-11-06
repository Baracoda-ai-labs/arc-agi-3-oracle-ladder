"""Sonde d'un objet dont le retrait contrefactuel libère une transition."""

import copy

import numpy as np
from apprentissage_regles import activation
from experience_regles_bp35 import cle
from interventions_elargies import InterventionsElargies, tags_ast
from perception_hierarchique import decomposer

from chrysalide.langue import depuis_python


def proposer(image, h, cs, known, offre, temporel, horloge, types_testes):
    if len(h.actives()) != 1 or 6 not in offre or not cs:
        return None
    sc, parents = decomposer(image, h.modele)
    if any(activation(c["python"], [sc]) for c in cs.values()):
        return None
    model = InterventionsElargies(image, h, cs, offre, horizon=2, scene_factory=lambda im, m: sc)
    tags = set().union(*(tags_ast(depuis_python(c["python"])) for c in cs.values())) - {"controle"}
    parent_ids = {o["attrs"].get("parent") for o in sc.sprites if set(o.get("tags", ())) & tags}
    bottom = model.actor["y"] + model.actor["pixels"].shape[0] - 1
    marge = min(horloge.prevoir(temporel, 0), horloge.prevoir(temporel, 1)) - bottom - 1
    if marge <= 2 * max(abs(v) for v in horloge.deltas.values()):
        return None
    for a in model.actions(model.depart):
        if isinstance(a, tuple):
            continue
        blocked = model.pas(model.depart, a)
        if all(i == "continue" for i in blocked[2]):
            continue
        for parent in parents:
            typ = parent["attrs"]["type_candidat"]
            if parent["nom"] not in parent_ids or typ in types_testes:
                continue
            alternative = copy.copy(model)
            alternative.scene = copy.deepcopy(sc)
            alternative.scene.sprites = [o for o in alternative.scene.sprites if o["attrs"].get("parent") != parent["nom"]]
            alternative.cache = {}
            alternative.predictions_cache = {}
            counter = alternative.pas(alternative.depart, a)
            if any(i != "continue" for i in counter[2]):
                continue
            ys, xs = np.nonzero(parent["pixels"] >= 0)
            mid = min(range(len(xs)), key=lambda i: (xs[i] - np.mean(xs)) ** 2 + (ys[i] - np.mean(ys)) ** 2)
            action = ["clic", int(parent["x"] + xs[mid]), int(parent["y"] + ys[mid])]
            if cle(image, action) in known:
                continue
            return {
                "plan": [action],
                "raison": "sonde_obstacle_contact",
                "type_motif": typ,
                "marge_pixels": marge,
                "action_liberee_si_retrait": a,
                "issues_avant": dict(zip(cs, blocked[2])),
                "issues_si_retrait": dict(zip(cs, counter[2])),
                "parent": {"x": int(parent["x"]), "y": int(parent["y"])},
                "etapes": [{"predictions": dict.fromkeys(cs, "inconnue")}],
                "portee": "retrait seulement contrefactuel ; effet du clic inconnu, aucun déplacement vers contact autorisé",
            }
    return None
