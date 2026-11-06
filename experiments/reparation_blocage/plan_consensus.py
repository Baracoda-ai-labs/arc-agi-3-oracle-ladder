"""Progresser sous accord de toutes les clauses ; l'absence de clause n'est pas sécurité."""

from collections import deque

from experience_bfws import ExperienceLocale
from experience_regles_bp35 import cle
from perception_hierarchique import decomposer


def chercher_modele(model, interdit=(), max_noeuds=6000, buts=()):
    queue = deque([(model.depart, [])])
    vus = {model.depart[:3]}
    best = None
    nodes = 0
    while queue and nodes < max_noeuds:
        s, path = queue.popleft()
        nodes += 1
        for a in model.actions(s):
            if not path and str(list(a) if isinstance(a, tuple) else a) in interdit:
                continue
            t = model.pas(s, a)
            if t is None or not t[2] or any(x != "continue" for x in t[2]):
                continue
            p = path + [a]
            key = t[:3]
            if key in vus:
                continue
            vus.add(key)
            gain = model.g * (t[0][1] - model.start[1])
            score = (t[0] in buts, gain, -len(p))
            if (gain > 0 or t[0] in buts) and (best is None or score > best[0]):
                best = (score, p, t)
            queue.append((t, p))
    return {
        "plan": best[1] if best else None,
        "gain_gravite": best[0][1] if best else 0,
        "destination": best[2][0] if best else None,
        "noeuds": nodes,
        "tronque": bool(queue),
    }


def decision(image, h, cs, known, remaining, offre=(3, 4, 6)):
    if not cs:
        return {"plan": None, "raison": "couverture_absente"}
    model = ExperienceLocale(image, h, cs, offre, horizon=min(12, remaining), scene_factory=lambda im, m: decomposer(im, m)[0])
    interdit = {
        str(list(a) if isinstance(a, tuple) else a)
        for a in model.actions(model.depart)
        if cle(image, list(a) if isinstance(a, tuple) else a) in known
    }
    result = chercher_modele(model, interdit)
    cur = model.depart
    steps = []
    for a in result["plan"] or []:
        cur = model.pas(cur, a)
        steps.append({"position": cur[0], "predictions": dict(zip(cs, cur[2], strict=True))})
    return {
        **result,
        "etapes": steps,
        "raison": "progres_consensus" if result["plan"] else "aucun_progres_consensus",
        "portee": "accord de clauses partielles, pas preuve de sécurité réelle ni but identifié",
    }
