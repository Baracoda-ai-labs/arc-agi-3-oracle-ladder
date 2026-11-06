# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — collecte de transitions dans le vrai moteur (arc_agi hors ligne), découpées par niveau et par vie.
Une action est un entier 1..7 ou ('clic', x, y) en pixels pour ACTION6. Seule l'image finale de chaque coup est gardée."""
import logging
from pathlib import Path

from arc_agi import Arcade, OperationMode
from arcengine.enums import GameAction, GameState

logging.disable(logging.INFO)
_ARCADES = {}


def environnement(gid, dossier):
    d = str(Path(dossier).resolve())
    if d not in _ARCADES:
        _ARCADES[d] = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=d)
    return _ARCADES[d].make(gid)


def en_pixels(a):
    """[6, x, y, n] (format solutions.json de B : case x, y d'une grille n × n) → ('clic', px, py) ; le reste inchangé."""
    if isinstance(a, list):
        _, x, y, n = a
        k = 64 // n
        pad = (64 - n * k) // 2
        return ("clic", pad + x * k + k // 2, pad + y * k + k // 2)
    return a


def jouer_action(env, a):
    a = en_pixels(a)
    if isinstance(a, tuple):
        return env.step(GameAction.ACTION6, data={"x": a[1], "y": a[2]})
    return env.step(GameAction.from_id(a))


def segments(gid, dossier, actions, env=None):
    """Joue `actions` depuis RESET. Renvoie des segments {grilles, actions, issue, finale, niveau} :
    len(grilles) == len(actions) + 1 ; `finale` est l'action qui a fini le segment (issue 'niveau', 'gagne' ou 'perdu'),
    sa transition n'est pas gardée (l'image suivante est un autre niveau ou un écran de fin)."""
    env = env or environnement(gid, dossier)
    f = env.reset()
    segs, gs, acts = [], [f.frame[-1]], []
    for a in map(en_pixels, actions):
        n0 = f.levels_completed
        f = jouer_action(env, a)
        issue = ("gagne" if f.state == GameState.WIN else "perdu" if f.state == GameState.GAME_OVER
                 else "niveau" if f.levels_completed > n0 else None)
        if issue:
            segs.append({"grilles": gs, "actions": acts, "issue": issue, "finale": a, "niveau": n0})
            if issue == "gagne":
                return segs
            if issue == "perdu":
                f = env.step(GameAction.RESET)
            gs, acts = [f.frame[-1]], []
        else:
            gs.append(f.frame[-1])
            acts.append(a)
    segs.append({"grilles": gs, "actions": acts, "issue": None, "finale": None, "niveau": f.levels_completed})
    return segs
