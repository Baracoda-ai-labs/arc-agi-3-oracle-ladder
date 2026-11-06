"""Nouveauté locale utile plutôt que nouveauté de l'image globale animée."""

import hashlib
import json


def signature(image, m, action, hypotheses):
    grid, (x, y), _ = m.lire(image)
    patch = grid[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2]
    return hashlib.sha256(json.dumps([x, y, patch.tolist(), action, sorted(hypotheses)], default=int).encode()).hexdigest()


class GardeOscillations:
    def __init__(self):
        self.vus = set()

    def refuse(self, key, action, gain=0, retour=False, progres=False):
        return action in (3, 4) and key in self.vus and gain <= 0 and not retour and not progres

    def enregistrer(self, key):
        self.vus.add(key)
