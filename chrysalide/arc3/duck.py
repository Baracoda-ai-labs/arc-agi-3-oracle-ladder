# SPDX-License-Identifier: MIT-0
"""« Notre Duck » : réimplémentation en salle blanche (S1, option b, CW-022) de l'approche décrite publiquement par Tufa Labs
(billet + README) — jamais à partir de leur code. Le modèle reçoit l'état du jeu et un unique outil Python éphémère :
il écrit du code qui inspecte la grille (texte, segmentation en objets, historique) et appelle `action(...)`.
Les plus anciens messages sont évincés pour garder un contexte court. Licence MIT-0."""
import builtins
import json
import re
import signal
import time
from collections import Counter

ACTIONS = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5, "MOUSE": 6, "UNDO": 7}
NOMS = {v: k for k, v in ACTIONS.items()}
IMPORTS_PERMIS = {"math", "itertools", "collections", "statistics", "re", "json", "functools", "heapq", "random"}

CONSIGNE = """You are playing an unknown turn-based puzzle game on a 64x64 grid of colors 0-15. No rules or goal are given:
discover them by experimenting, then finish each level with as few actions as possible (efficiency is scored).
You have ONE tool: write Python code in a single ```python block. Each block runs in a FRESH namespace with:
- current_frame.ascii (list of 64 strings, one hex digit per cell), current_frame.segmentation (list of objects: color, cells, bbox, size, shape_hash)
- previous_frame, history (list of past actions and effects), last_transition (cells that changed), valid_actions
- action(name, row=None, col=None): name in UP, DOWN, LEFT, RIGHT, SPACE, MOUSE (needs row, col), UNDO. Returns a dict with
  board_changed, cells_changed, level_completed, game_over, levels_completed. You may call action() several times in one block.
Use print() to see results (output is truncated). Keep notes in your messages: older messages will be dropped."""


class Delai(Exception):
    pass


def segmentation(grille):
    """Composantes connexes (4-voisinage) par couleur, triées par taille décroissante. Le fond (plus grande couleur) est exclu."""
    h, w = len(grille), len(grille[0])
    fond = Counter(v for r in grille for v in r).most_common(1)[0][0]
    vu, objets = set(), []
    for i in range(h):
        for j in range(w):
            if (i, j) in vu or grille[i][j] == fond:
                continue
            c, pile, cellules = grille[i][j], [(i, j)], []
            vu.add((i, j))
            while pile:
                a, b = pile.pop()
                cellules.append((a, b))
                for x, y in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= x < h and 0 <= y < w and (x, y) not in vu and grille[x][y] == c:
                        vu.add((x, y))
                        pile.append((x, y))
            r0, c0 = min(a for a, _ in cellules), min(b for _, b in cellules)
            r1, c1 = max(a for a, _ in cellules), max(b for _, b in cellules)
            forme = tuple(sorted((a - r0, b - c0) for a, b in cellules))
            objets.append({"color": c, "size": len(cellules), "bbox": (r0, c0, r1, c1), "cells": cellules,
                           "shape_hash": hash(forme) & 0xFFFFFF})
    return sorted(objets, key=lambda o: -o["size"])


class Vue:
    def __init__(self, grille):
        self.grid = [list(r) for r in grille]
        # liste de 64 chaînes (une par rangée) : un texte unique se faisait parcourir caractère par caractère (essai 27B du 04/10)
        self.ascii = ["".join(f"{v:x}" for v in r) for r in grille]
        self._seg = None

    @property
    def segmentation(self):
        if self._seg is None:
            self._seg = segmentation(self.grid)
        return self._seg


class Partie:
    """Fait le lien entre le code du modèle et l'environnement : `action()` joue un vrai coup et journalise."""

    def __init__(self, env, frame, max_actions):
        self.env, self.f, self.max_actions = env, frame, max_actions
        self.history, self.n_actions, self.prev = [], 0, None

    def action(self, name, row=None, col=None):
        from arcengine.enums import GameAction, GameState
        name = str(name).upper()
        if name not in ACTIONS:
            raise ValueError(f"unknown action {name}")
        aid = ACTIONS[name]
        if aid not in self.f.available_actions:
            return {"error": f"{name} not valid now; valid: {[NOMS[a] for a in self.f.available_actions]}"}
        if self.n_actions >= self.max_actions:
            return {"error": "action budget exhausted"}
        avant = self.f
        if aid == 6:
            if row is None or col is None:
                return {"error": "MOUSE needs row and col"}
            f = self.env.step(GameAction.from_id(6), data={"x": int(col) % 64, "y": int(row) % 64})
        else:
            f = self.env.step(GameAction.from_id(aid))
        self.n_actions += 1
        g0, g1 = avant.frame[-1], f.frame[-1]
        diff = [(i, j) for i in range(64) for j in range(64) if g0[i][j] != g1[i][j]]
        res = {"action": name, "board_changed": bool(diff), "cells_changed": len(diff),
               "level_completed": f.levels_completed > avant.levels_completed, "game_over": f.state == GameState.GAME_OVER,
               "levels_completed": f.levels_completed, "won": f.state == GameState.WIN}
        self.history.append({**res, **({"row": row, "col": col} if aid == 6 else {})})
        self.prev, self.f, self.last_diff = avant, f, diff
        if res["game_over"]:
            self.f = self.env.step(GameAction.RESET)
            res["note"] = "game over: level restarted"
        return res


def executer(code, partie, delai=30, max_sortie=3000):
    """Exécute un bloc dans un espace de noms NEUF, imports limités, délai par signal. Renvoie le texte imprimé (tronqué)."""
    sortie = []

    def imprimer(*a, **k):
        sortie.append(" ".join(str(x) for x in a))

    def importer(nom, *a, **k):
        if nom.split(".")[0] not in IMPORTS_PERMIS:
            raise ImportError(f"import of {nom} not allowed")
        return builtins.__import__(nom, *a, **k)
    sures = {k: getattr(builtins, k) for k in ("abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "len",
                                                 "list", "map", "max", "min", "range", "reversed", "round", "set", "sorted", "str",
                                                 "sum", "tuple", "zip", "isinstance", "ValueError", "Exception", "print", "type", "repr", "hasattr",
                                                 "divmod", "pow", "iter", "next", "slice", "chr", "ord", "format", "KeyError",
                                                 "IndexError", "TypeError", "frozenset", "callable")}
    sures.update({"print": imprimer, "__import__": importer})
    ns = {"__builtins__": sures, "current_frame": Vue(partie.f.frame[-1]),
          "previous_frame": Vue(partie.prev.frame[-1]) if partie.prev else None, "history": list(partie.history),
          "last_transition": list(getattr(partie, "last_diff", [])), "action": partie.action,
          "valid_actions": [NOMS[a] for a in partie.f.available_actions], "levels_completed": partie.f.levels_completed}

    def sonne(*_):
        raise Delai()
    ancien = signal.signal(signal.SIGALRM, sonne)
    signal.alarm(delai)
    try:
        exec(compile(code, "<duck>", "exec"), ns)  # noqa: S102 — bac à sable volontaire (imports filtrés, délai)
        if "result" in ns:
            sortie.append(f"result = {ns['result']!r}")
    except Delai:
        sortie.append(f"[timeout after {delai}s]")
    except Exception as e:  # noqa: BLE001 — l'erreur du code du modèle lui est rendue
        sortie.append(f"[error] {type(e).__name__}: {e}")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, ancien)
    t = "\n".join(sortie)
    return t if len(t) <= max_sortie else t[:max_sortie] + "\n[output truncated]"


BLOC = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)  # tolère ```py et ``` sans langage


def jouer(env, gen, max_actions=400, max_tours=200, garder=8, plafond_s=1800, journal=None):
    """Un passage de jeu. `gen(messages) -> texte` (modèle). Renvoie les statistiques du passage."""
    f = env.reset()
    partie = Partie(env, f, max_actions)
    msgs, t0, tours, outils, sortie = [], time.perf_counter(), 0, 0, ""
    while tours < max_tours and partie.f.state.name != "WIN" and partie.n_actions < max_actions:
        if time.perf_counter() - t0 > plafond_s:
            break
        etat = (f"Levels completed: {partie.f.levels_completed}/{partie.f.win_levels}. Actions used: {partie.n_actions}. "
                f"Valid actions: {[NOMS[a] for a in partie.f.available_actions]}.")
        # un seul message utilisateur par tour : sortie de l'outil du tour précédent + état (alternance stricte)
        msgs.append({"role": "user", "content": (sortie + "\n\n" + etat) if msgs else CONSIGNE + "\n\n" + etat})
        sortie = "(no python block in your last message)"
        contexte = msgs[:1] + msgs[1:][-2 * garder:] if len(msgs) > 2 * garder + 1 else msgs  # éviction des plus anciens
        rep = gen(list(contexte))  # copie : le modèle ne voit jamais une liste modifiée après coup
        tours += 1
        msgs.append({"role": "assistant", "content": rep})
        m = BLOC.search(rep)
        if m:
            outils += 1
            sortie = "Tool output:\n" + executer(m.group(1), partie)
        if journal:
            journal({"tour": tours, "actions": partie.n_actions, "niveaux": partie.f.levels_completed, "code": bool(m),
                     "reponse": rep[-1500:], "sortie_outil": sortie[:1500] if m else ""})
    return {"niveaux": partie.f.levels_completed, "niveaux_total": partie.f.win_levels, "etat": partie.f.state.name,
            "actions": partie.n_actions, "tours": tours, "appels_outil": outils, "mur_s": time.perf_counter() - t0}


def json_dump(x):
    return json.dumps(x, ensure_ascii=False)
