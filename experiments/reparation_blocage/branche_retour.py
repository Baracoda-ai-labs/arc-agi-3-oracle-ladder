"""Branche inédite avec route de retrait explicite dans le modèle partiel."""

from collections import deque

from experience_bfws import techniques


def retour(model, state, cible):
    def safe(s):
        return [a for a in model.actions(s) if all(v == "continue" for v in model.pas(s, a)[2])]

    return techniques().bfs(state, model.pas, safe, lambda s: s[0] == cible, max_noeuds=1000)


def chercher(model, interdits=(), budget=16):
    q = deque([(model.depart, [])])
    seen = {model.depart[:3]}
    best = None
    nodes = 0
    while q and nodes < 3000:
        s, path = q.popleft()
        nodes += 1
        if len(path) >= 8:
            continue
        for a in model.actions(s):
            if not path and str(list(a) if isinstance(a, tuple) else a) in interdits:
                continue
            t = model.pas(s, a)
            if t is None or any(v != "continue" for v in t[2]) or t[:3] in seen:
                continue
            # Gravité fixe monotone : changer de hauteur ne permet pas de retrouver l'ancre.
            if t[0][1] != model.start[1]:
                continue
            seen.add(t[:3])
            p = path + [a]
            back = retour(model, t, model.start)
            if back is not None and t[0] != model.start and len(p) + len(back) <= budget:
                score = (abs(t[0][0] - model.start[0]), -len(p) - len(back))
                if best is None or score > best[0]:
                    best = (score, p, back, t)
            q.append((t, p))
    return {
        "plan": best[1] if best else None,
        "retour": best[2] if best else None,
        "destination": best[3][0] if best else None,
        "noeuds": nodes,
        "tronque": bool(q),
        "portee": "retour spatial au même point, décor modifié conservé ; modèle conditionnel",
    }
