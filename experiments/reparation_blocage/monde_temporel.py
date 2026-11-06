"""État dynamique observable, hypothèses d'horloge et veto de contact prospectif."""

import copy
from dataclasses import dataclass

import numpy as np
from apprentissage_regles import activation
from perception_hierarchique import decomposer

from chrysalide.arc3.films import composantes


@dataclass(frozen=True)
class Front:
    couleur: int
    haut: int
    pixels: int
    largeur: int


def front(image, couleur):
    mask = image[:-1] == couleur
    if not mask.any():
        return None
    # Conserver la composante dominante, sans imposer une couleur/position de jeu.
    comp = max(composantes(mask), key=len)
    xs = [x for x, y in comp]
    ys = [y for x, y in comp]
    return Front(int(couleur), min(ys), int(mask.sum()), max(xs) - min(xs) + 1)


def front_etendu(image, couleur):
    # Motifs pointillés : union des composantes de même couleur, identité hypothétique.
    ys, xs = np.nonzero(image[:-1] == couleur)
    if not len(ys):
        return None
    return Front(int(couleur), int(ys.min()), len(ys), int(xs.max() - xs.min() + 1))


def ajuster(transitions):
    """Transitions (rang absolu, action, delta). Pas d'inférence avant apparition."""
    models = []
    for nom, cle in [("action", lambda i, a: str(a)), ("phase_2", lambda i, a: str(i % 2))]:
        table = {}
        compatible = True
        for i, a, delta in transitions:
            k = cle(i, a)
            if k in table and table[k] != delta:
                compatible = False
            table[k] = delta
        if compatible:
            models.append({"type": nom, "deltas": table, "supports": len(transitions)})
    return models


def predire(models, etat, action, rang):
    predictions = {}
    for model in models:
        key = str(action) if model["type"] == "action" else str(rang % 2)
        delta = model["deltas"].get(key)
        predictions[model["type"]] = None if delta is None else etat.haut + delta
    vals = [v for v in predictions.values() if v is not None]
    return {
        "predictions": predictions,
        "couvert": bool(models) and len(vals) == len(models),
        "intervalle": [min(vals), max(vals)] if vals else None,
        "portee": "hypothèses locales de bord visible, pas simulateur pixel ni loi causale",
    }


def risque_contact(image, m, h, clauses, etat, hauts, action):
    """Projection conservative d'une région dynamique, programmes natifs inchangés."""
    origin_scene, _ = decomposer(image, m)
    results = []
    for name in h.actives():
        position = h.predire(image, action, name)
        x, y = position["position"]
        ox, oy = position["origine"]
        cx, cy = m.position(image)
        for haut in hauts:
            sc = copy.deepcopy(origin_scene)
            for o in sc.sprites:
                if "controle" in o.get("tags", ()):
                    o["x"] += ox + x * m.pas + m.pas // 2 - cx
                    o["y"] += oy + y * m.pas + m.pas // 2 - cy
                elif f"couleur_{etat.couleur}" in o.get("tags", ()) and o["y"] >= etat.haut:
                    o["y"] += haut - etat.haut
            issues = {n: (activation(c["python"], [sc]) or {}).get("issue", "continue") for n, c in clauses.items()}
            results.append({"dynamique": name, "haut_projete": haut, "issues": issues})
    return {
        "risque": any(v != "continue" for r in results for v in r["issues"].values()),
        "details": results,
        "portee": "projection des parties visibles vers bord prévu, occlusions et croissance exacte inconnues",
    }


class EtatTemporel:
    """Couche d'état du pilote : front, rang, transitions et horloges concurrentes."""

    def __init__(self, image):
        self.couleurs_initiales = set(map(int, np.unique(image[:-1])))
        self.etat = None
        self.rang = 0
        self.transitions = []
        self.modeles = []
        self.front_perdu = False

    def observer(self, avant, apres, action, modele):
        from boucle_navigation_visible import decalage

        self.rang += 1
        if self.etat is None:
            for c in sorted(set(map(int, np.unique(apres[:-1]))) - self.couleurs_initiales):
                f = front_etendu(apres, c)
                if f.largeur >= apres.shape[1] // 2 and f.pixels >= apres.shape[1]:
                    self.etat = f
                    self.front_perdu = False
                    break
        else:
            f = front_etendu(apres, self.etat.couleur)
            if f is None:
                self.modeles = []
                self.etat = None
                self.transitions = []
                self.front_perdu = True
                return {"statut": "front_perdu", "rang": self.rang}
            dy, err = decalage(avant, apres, modele.palette)
            if err <= 0.15:
                self.transitions.append((self.rang, action, f.haut - self.etat.haut - dy))
                self.modeles = ajuster(self.transitions) if len(self.transitions) >= 2 else []
            else:
                self.modeles = []
            self.etat = f
        return {
            "rang": self.rang,
            "front": None if self.etat is None else self.etat.__dict__,
            "modeles": self.modeles,
            "portee": "couverture partielle des nouvelles régions étendues",
        }

    def evaluer(self, image, modele, h, clauses, action):
        if self.etat is None:
            return {
                "admissible": not self.front_perdu,
                "statut": "front_perdu" if self.front_perdu else "aucun_front_detecte",
                "garantie": False,
            }
        p = predire(self.modeles, self.etat, action, self.rang + 1)
        if not p["couvert"]:
            return {"admissible": False, "statut": "evolution_non_couverte", "prevision": p}
        r = risque_contact(image, modele, h, clauses, self.etat, p["intervalle"], action)
        return {"admissible": not r["risque"], "statut": "projection_dynamique", "prevision": p, **r}
