"""Rejeu hors ligne d'une partie enregistrée à travers l'agent (aucun coup réel) : débogage et tests reproductibles.

`LabRejoue` imite `Laboratoire` : il rend les images enregistrées tant que l'action demandée est celle de la trace.
"""
import json
from pathlib import Path
import numpy as np


class Divergence(Exception):
    pass


class EcoNeutre:
    valid = False; last = None
    def admissible(self, seq): return True
    def cost_upper(self, seq): return float(len(seq))
    def report(self): return {}


class LabRejoue:
    def __init__(self, dossier):
        d = Path(dossier); z = np.load(d / 'partie.npz')
        self.trace_images = z['images']; self.trace_actions = json.load(open(d / 'partie.json'))['actions']
        self.images = [self.trace_images[0].copy()]; self.image = self.images[0].copy(); self.rows = []
        self.finished = False; self.won = False; self.injected = True
        self.victoire_trace = bool(json.load(open(d / 'partie.json')).get('victory'))
        try:
            from boucle_v4.economie import Economie
            self.economy = Economie(self.image)
        except Exception:
            self.economy = EcoNeutre()

    def play(self, a, purpose=''):
        t = len(self.rows)
        if t >= len(self.trace_actions) or self.trace_actions[t] != a:
            raise Divergence(f'pas {t + 1} : action {a} ≠ trace {self.trace_actions[t] if t < len(self.trace_actions) else None}')
        avant = self.image
        self.image = self.trace_images[t + 1].copy(); self.images.append(self.image.copy())
        if t + 1 == len(self.trace_actions) and self.victoire_trace:
            self.won = self.finished = True
        if hasattr(self.economy, 'update'):
            self.economy.update(a, avant, self.image, self.finished, self.won)
        self.rows.append(dict(step=t + 1, action=a, purpose=purpose, levels_completed=0, state='rejeu'))
        return self.image, np.asarray([self.image])

    def save(self):
        pass


def agent_au_pas(dossier, k, sortie, **kw):
    """Agent dont l'état reflète les k premiers coups de la trace."""
    from .agent import Agent
    lab = LabRejoue(dossier)
    ag = Agent('g50t', 6, 'jeux', sortie, lab=lab, **kw)
    ag.model = None
    for a in lab.trace_actions[:4]:
        from boucle_v4.fantome_general import FantomeGeneral
        b = lab.image.copy(); im, _ = lab.play(a, 'identifier')
        try:
            ag.model = FantomeGeneral(b, im, a); break
        except Exception:
            continue
    ag.init_suivi(); ag.mettre_a_jour_hypotheses()
    while len(lab.rows) < k:
        a = lab.trace_actions[len(lab.rows)]
        lab.play(a, 'rejeu'); ag.avancer_suivi(len(lab.rows)); ag.mettre_a_jour_hypotheses()
    return ag
