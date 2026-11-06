"""Matrices de désaccord : séparer géométrie possible, film observé et accès par actions."""

import math
from collections import Counter

import numpy as np


def partitions(matrice):
    a = np.asarray(matrice, dtype=bool)
    if a.ndim != 2:
        raise ValueError("Matrice expériences × hypothèses attendue")
    classes = {}
    for j in range(a.shape[1]):
        classes.setdefault(tuple(a[:, j]), []).append(j)
    patterns = Counter(tuple(row) for row in a)
    scores = []
    for row, count in patterns.items():
        n = len(row)
        k = sum(row)
        entropy = -sum(p * math.log2(p) for p in (k / n, 1 - k / n) if p)
        scores.append({"predictions": list(map(bool, row)), "nombre": count, "entropie_convention_uniforme": entropy})
    return {
        "classes_indiscernables": [x for x in classes.values()],
        "distance_hamming": [[int(np.sum(a[:, i] != a[:, j])) for j in range(a.shape[1])] for i in range(a.shape[1])],
        "partitions": sorted(scores, key=lambda s: -s["entropie_convention_uniforme"]),
        "lignes": len(a),
        "colonnes": a.shape[1],
    }


def tuiles_multicolores(image, modele):
    _, _, (ox, oy) = modele.lire(image)
    s = modele.pas
    groups = {}
    for y in range(oy, 63 - s + 1, s):
        for x in range(ox, 64 - s + 1, s):
            patch = image[y : y + s, x : x + s]
            signature = tuple(map(tuple, patch.tolist()))
            groups.setdefault(signature, []).append([x, y])
    return [
        {
            "pixels": list(map(list, pattern)),
            "couleurs": sorted({v for row in pattern for v in row}),
            "occurrences": coords,
            "portee": "hypothèse de motif aligné sur grille apprise, pas identité causale",
        }
        for pattern, coords in groups.items()
        if len({v for row in pattern for v in row}) > 1
    ]


def signature_issue(value):
    import json

    return json.dumps(value, sort_keys=True, default=int, separators=(",", ":"))


def classer_experiences(experiences, hypotheses, reserve):
    """Gain/coût sur un même ensemble de modèles ; aucune autorisation d'action."""
    names = set(hypotheses)
    if not names or reserve < 0:
        raise ValueError("Hypothèses et budget requis")
    scored = []
    refused = []
    for e in experiences:
        predictions = e.get("predictions", {})
        if set(predictions) != names or any(v is None for v in predictions.values()):
            refused.append({"id": e["id"], "raison": "predictions_incompletes_ou_autre_espace"})
            continue
        cout = e.get("cout_actions", 0) + e.get("cout_acces", 0)
        if not math.isfinite(cout) or cout <= 0 or cout > reserve or not e.get("accessible", False):
            refused.append({"id": e["id"], "raison": "cout_ou_acces_non_admissible"})
            continue
        groups = Counter(signature_issue(v) for v in predictions.values())
        if len(groups) < 2:
            refused.append({"id": e["id"], "raison": "aucun_departage"})
            continue
        n = len(names)
        info = -sum((v / n) * math.log2(v / n) for v in groups.values())
        scored.append(
            {
                **e,
                "cout_total": cout,
                "information_convention_uniforme": info,
                "score_information_par_coup": info / cout,
                "pire_nombre_restant": max(groups.values()),
                "risque": e.get("risque", "inconnu"),
                "droit_action": False,
            }
        )
    scored.sort(key=lambda e: (-e["score_information_par_coup"], e["pire_nombre_restant"], e["cout_total"], str(e["id"])))
    return {
        "classement": scored,
        "refus": refused,
        "choix": scored[0] if scored else None,
        "limite": "poids uniformes non calibrés ; risque conservé séparément ; pas optimalité globale",
    }


def reduire_espace(predictions, observation):
    """Incohérence globale ouvre une réparation ; jamais choisir le moins faux."""
    survivors = [n for n, p in predictions.items() if p is not None and signature_issue(p) == signature_issue(observation)]
    unknown = [n for n, p in predictions.items() if p is None]
    return {
        "compatibles": survivors,
        "inconnues": unknown,
        "refutees": [n for n in predictions if n not in survivors + unknown],
        "statut": "hors_couverture" if not survivors and not unknown else "espace_reduit",
        "regle_prouvee": False,
    }
