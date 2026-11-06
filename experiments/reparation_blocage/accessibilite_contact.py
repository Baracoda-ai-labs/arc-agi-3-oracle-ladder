"""Distinguer désaccord au milieu d'un déplacement et expérience exécutable."""

import copy
from collections import Counter


def trajet(debut, fin, pas):
    x, y = debut[0] * pas, debut[1] * pas
    for axe, delta in ((0, (fin[0] - debut[0]) * pas), (1, (fin[1] - debut[1]) * pas)):
        for _ in range(abs(delta)):
            signe = 1 if delta > 0 else -1
            if axe == 0:
                x += signe
            else:
                y += signe
            yield (x, y), ("droite" if signe > 0 else "gauche") if axe == 0 else ("bas" if signe > 0 else "haut")


def resume_trajet(signatures):
    if not signatures:
        return {"issues": [], "passages_separateurs": [], "separation_fin": False}
    cumule = [False] * len(signatures[0])
    passages = []
    for i, row in enumerate(signatures):
        cumule = [a or b for a, b in zip(cumule, row, strict=True)]
        if len(set(cumule)) > 1:
            passages.append(i)
    return {
        "issues": ["defaite" if x else "continue" for x in cumule],
        "passages_separateurs": passages,
        "separation_fin": len(set(cumule)) > 1,
    }


def auditer(model, enveloppe):
    if enveloppe["statut"] == "non_applicable" or model.blocks & model.affectables:
        return {"statut": "non_applicable"}
    sc = copy.deepcopy(model.scene)
    acteur = next(o for o in sc.sprites if "controle" in o.get("tags", ()))
    base = (acteur["x"] - model.start[0] * model.m.pas, acteur["y"] - model.start[1] * model.m.pas)
    cache = {}
    records = []
    approches = Counter()
    erreurs = 0

    def signature(p):
        if p not in cache:
            acteur["x"], acteur["y"] = base[0] + p[0], base[1] + p[1]
            found = []
            for program in model.programmes.values():
                sc.issue = None
                program.step(sc, ("OBSERVE",))
                found.append(sc.issue == "defaite")
            cache[p] = found
        return cache[p]

    for e in enveloppe["aretes"]:
        points = list(trajet(e["depart"], e["arrivee"], model.m.pas))
        sig = [signature(p) for p, d in points]
        r = resume_trajet(sig)
        issues = r["issues"] if sig else ["continue"] * len(model.ids)
        erreurs += issues != [e["issues"][n] for n in model.ids]
        if r["passages_separateurs"]:
            positions = [points[i] for i in r["passages_separateurs"]]
            approches.update(d for p, d in positions)
            records.append(
                {
                    "depart": e["depart"],
                    "arrivee": e["arrivee"],
                    **r,
                    "positions_separatrices": [p for p, d in positions],
                    "directions": [d for p, d in positions],
                    "positions_sur_grille": [p for p, d in positions if p[0] % model.m.pas == 0 and p[1] % model.m.pas == 0],
                }
            )
    return {
        "statut": "analyse_conditionnelle",
        "erreurs_contre_cache": erreurs,
        "aretes": len(enveloppe["aretes"]),
        "positions_pixels_evaluees": len(cache),
        "transits_separateurs": records,
        "directions": dict(approches),
        "experiences_separatrices_fin_action": sum(r["separation_fin"] for r in records),
        "limite": "pas spatiaux, pas durée en frames ; enveloppe permissive du modèle, non preuve dans le vrai jeu",
    }
