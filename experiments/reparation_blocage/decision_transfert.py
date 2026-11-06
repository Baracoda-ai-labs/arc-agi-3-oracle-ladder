"""Réouverture des dynamiques et choix d'une expérience sous consensus de contact."""

from types import SimpleNamespace

from apprentissage_regles import activation
from experience_regles_bp35 import cle
from garde_oscillations import signature
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer
from plan_remontee import decision as progres


def decision(image, h, cs, known, remaining, offre, garde=None, temporel=None):
    if len(h.actives()) == 1:
        result = progres(image, h, cs, known, remaining, offre)
        if result.get("plan") and temporel is not None:
            t = temporel.evaluer(image, h.modele, h, cs, result["plan"][0])
            result["controle_temporel"] = t
            if not t["admissible"]:
                result.update(plan=None, raison="refus_dynamique_du_decor")
        return result
    if not h.actives():
        return {"plan": None, "raison": "catalogue_refute"}
    proposal = h.proposer(image, offre)
    for c in proposal["experiences_candidates"]:
        action = c["action"]
        normal = list(action) if isinstance(action, tuple) else action
        if cle(image, normal) in known:
            continue
        if garde is not None and garde.refuse(signature(image, h.modele, normal, h.actives()), normal, c["gain_minimax"]):
            continue
        temporel_check = temporel.evaluer(image, h.modele, h, cs, normal) if temporel is not None else None
        if temporel_check is not None and not temporel_check["admissible"]:
            continue
        a = tuple(action) if isinstance(action, list) else action
        checks = {}
        ok = True
        for name in h.actives():
            local = SimpleNamespace(modele=h.modele, catalogue=h.catalogue, actives=lambda n=name: [n], scene=h.scene)
            m = InterventionsElargies(image, local, cs, offre, horizon=2, scene_factory=lambda im, mo: decomposer(im, mo)[0])
            if a in m.actions(m.depart):
                issues = m.pas(m.depart, a)[2]
            elif tuple(c["predictions"][name]["position"]) == m.start and c["predictions"][name]["retire"] is None:
                issues = tuple((activation(x["python"], [m.scene]) or {}).get("issue", "continue") for x in cs.values())
            else:
                ok = False
                break
            checks[name] = dict(zip(cs, issues))
            if any(v != "continue" for v in issues):
                ok = False
                break
        if ok:
            return {
                "plan": [normal],
                "raison": "experience_dynamique_rouverte",
                "hypotheses": h.actives(),
                "gain_minimax": c["gain_minimax"],
                "controle_temporel": temporel_check,
                "predictions_dynamique": c["predictions"],
                "checks": checks,
                "etapes": [{"predictions": dict.fromkeys(cs, "continue")}],
                "retrait": "non établi pendant désambiguïsation des dynamiques",
            }
    return {"plan": None, "raison": "aucune_experience_commune"}
