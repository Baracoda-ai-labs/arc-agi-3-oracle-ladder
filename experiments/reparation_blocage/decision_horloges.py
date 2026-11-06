"""Départager les horloges avec un coup admissible sous chaque hypothèse."""

from types import SimpleNamespace

from decision_transfert import decision as decision_navigation
from experience_regles_bp35 import cle
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer


def decision(image, h, cs, known, remaining, offre, garde=None, temporel=None):
    if temporel is not None and len(temporel.modeles) > 1:
        for action in (3, 4):
            if action not in offre or cle(image, action) in known:
                continue
            t = temporel.evaluer(image, h.modele, h, cs, action)
            predictions = t.get("prevision", {}).get("predictions", {})
            if not t["admissible"] or len(set(predictions.values())) < 2:
                continue
            checks = {}
            valide = True
            for n in h.actives():
                local = SimpleNamespace(modele=h.modele, catalogue=h.catalogue, actives=lambda n=n: [n], scene=h.scene)
                b = InterventionsElargies(image, local, cs, offre, horizon=2, scene_factory=lambda im, m: decomposer(im, m)[0])
                if action not in b.actions(b.depart):
                    valide = False
                    break
                u = b.pas(b.depart, action)
                checks[n] = dict(zip(cs, u[2]))
                if any(v != "continue" for v in u[2]):
                    valide = False
                    break
            if valide:
                return {
                    "plan": [action],
                    "raison": "departage_horloges",
                    "predictions_front": predictions,
                    "controle_temporel": t,
                    "checks_navigation": checks,
                    "gain_minimax": 1,
                    "etapes": [{"predictions": dict.fromkeys(cs, "continue")}],
                    "portee": "risque évalué dans deux modèles partiels, pas sécurité garantie",
                }
    return decision_navigation(image, h, cs, known, remaining, offre, garde, temporel)
