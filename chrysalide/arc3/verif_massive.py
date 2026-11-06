# SPDX-License-Identifier: MIT-0
"""T2.6 (CW-058, demande de Thomas) : vérification MASSIVE de règles candidates sur CPU, sans LLM et sans coup de jeu.
Une règle = `predire(grille, action) -> grille` (même forme qu'une fonction retenue du harnais de Franzen). On la confronte à
toutes les transitions déjà observées d'une partie (`*_events.jsonl` du harnais : grille après chaque coup) et on rend, par
règle : exactitude case par case (hors cases masquées = compteurs/barres appris, masque.py), première transition contredite,
classe d'erreur dominante. Évaluation en parallèle (multiprocessing, os.cpu_count() − 2 processus), délai max par appel.
Deux sources de règles : (1) des sources Python (celles qu'écrirait le LLM), exécutées dans un espace de noms vide ;
(2) un générateur paramétré SANS LLM (déplacement par couleur × direction × pas, bascule de voisins au clic, gravité,
téléportation au clic, identité) qui produit des milliers de candidates : c'est lui qui exerce les CPU sur le banc."""
import ast
import hashlib
import json
import os
import random as _random
import signal
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path as _Path

import numpy as np

from chrysalide.arc3.masque import Masque

DIRS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}
SIMPLES = ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")


# ---------------------------------------------------------------- transitions observées
def action_de(e):
    nom, aff = e.get("action_name", ""), e.get("action_display", "")
    if aff.startswith("MOUSE("):
        r, c = (int(x.split("=")[1]) for x in aff[6:-1].split(", "))
        return ("MOUSE", r, c)
    return ({"ACTION1": "UP", "ACTION2": "DOWN", "ACTION3": "LEFT", "ACTION4": "RIGHT", "ACTION5": "SPACE",
             "ACTION7": "UNDO"}.get(nom, aff or nom), None, None)


def transitions(chemin):
    """[(g0, action, g1)] dans une même vie et un même niveau (ni RESET, ni game over, ni changement de niveau)."""
    with open(chemin) as h:
        ev = [json.loads(ligne) for ligne in h]
    prec, niv, out = None, None, []
    for e in ev:
        if e.get("type") not in ("initial", "action") or "board" not in e:
            continue
        g = np.array(json.loads(e["board"]) if isinstance(e["board"], str) else e["board"], dtype=np.int8)
        if e.get("type") == "action":
            a = action_de(e)
            ok = (prec is not None and a[0] not in ("RESET", "UNDO") and e.get("level") == niv
                  and str(e.get("game_over")) != "True" and str(e.get("level_completed")) != "True")
            if ok:
                out.append((prec, a, g))
        prec, niv = g, e.get("level")
        if str(e.get("game_over")) == "True":
            prec = None
    return out


def masque_de(trans, mode="bordure", bord=4):
    """Cases ignorées dans la comparaison. « bordure » (défaut) : les `bord` cases du pourtour (barres, compteurs).
    « appris » : masque appris de B — à éviter ici : sur un jeu de déplacement, la trace du joueur forme une zone qui
    change à chaque coup et le masque couvre presque tout le plateau (ar25 : 3 899 cases sur 4 096 ; banc T2.6)."""
    if mode == "bordure":
        garde = np.zeros(trans[0][0].shape, dtype=bool)
        garde[bord:-bord, bord:-bord] = True
        return garde
    m = Masque()
    for g0, _, g1 in trans:
        m.observer(g0.tolist(), g1.tolist())
    garde = np.ones(trans[0][0].shape, dtype=bool) if trans else None
    for r, c in m.cellules():
        garde[r, c] = False
    return garde


# ---------------------------------------------------------------- générateur de règles sans LLM
def fond(g):
    v, n = np.unique(g, return_counts=True)
    return v[n.argmax()]


def regle_param(spec, g, a):
    """Applique une règle paramétrée `spec` à (g, a) et rend la grille prédite."""
    fam = spec[0]
    h = g.copy()
    if fam == "identite":
        return h
    if fam == "deplace":  # ("deplace", couleur, action, dr, dc, pas) : les cases de cette couleur bougent si action
        _, c, act, dr, dc, k = spec
        if a[0] != act:
            return h
        ys, xs = np.nonzero(g == c)
        if len(ys) == 0:
            return h
        b = fond(g)
        h[ys, xs] = b
        ny, nx = np.clip(ys + dr * k, 0, g.shape[0] - 1), np.clip(xs + dc * k, 0, g.shape[1] - 1)
        h[ny, nx] = c
        return h
    if fam == "bascule":  # ("bascule", c1, c2, rayon) : clic → les cases c1/c2 du voisinage s'échangent
        _, c1, c2, rad = spec
        if a[0] != "MOUSE":
            return h
        r, c = a[1], a[2]
        z = h[max(0, r - rad): r + rad + 1, max(0, c - rad): c + rad + 1]
        m1, m2 = z == c1, z == c2
        z[m1], z[m2] = c2, c1
        return h
    if fam == "gravite":  # ("gravite", couleur, action, dr, dc) : la couleur glisse jusqu'à un obstacle (non-fond)
        _, c, act, dr, dc = spec
        if a[0] != act:
            return h
        b = fond(g)
        for _ in range(max(g.shape)):
            ys, xs = np.nonzero(h == c)
            ny, nx = ys + dr, xs + dc
            ok = (ny >= 0) & (ny < g.shape[0]) & (nx >= 0) & (nx < g.shape[1])
            libre = np.zeros(len(ys), dtype=bool)
            libre[ok] = h[ny[ok], nx[ok]] == b
            if not libre.any():
                break
            h[ys[libre], xs[libre]] = b
            h[ny[libre], nx[libre]] = c
        return h
    if fam == "teleporte":  # ("teleporte", couleur) : clic → l'objet de cette couleur va à la case cliquée
        _, c = spec
        if a[0] != "MOUSE":
            return h
        ys, xs = np.nonzero(g == c)
        if len(ys) == 0:
            return h
        b = fond(g)
        h[ys, xs] = b
        ny = np.clip(ys - ys.min() + a[1], 0, g.shape[0] - 1)
        nx = np.clip(xs - xs.min() + a[2], 0, g.shape[1] - 1)
        h[ny, nx] = c
        return h
    raise ValueError(fam)


def generer(couleurs, actions_vues):
    """Toutes les candidates paramétrées pour ces couleurs et ces actions (des milliers)."""
    specs = [("identite",)]
    simples = [a for a in actions_vues if a in SIMPLES]
    for c in couleurs:
        for act in simples:
            for (dr, dc) in DIRS.values():
                for k in (1, 2, 3, 4, 5, 6, 8):
                    specs.append(("deplace", c, act, dr, dc, k))
                specs.append(("gravite", c, act, dr, dc))
        if "MOUSE" in actions_vues:
            specs.append(("teleporte", c))
            for c2 in couleurs:
                if c2 != c:
                    for rad in (0, 1, 2, 3):
                        specs.append(("bascule", c, c2, rad))
    return specs


# ---------------------------------------------------------------- évaluation (parallèle)
_T, _G = None, None


def _init(trans, garde):
    global _T, _G
    _T, _G = trans, garde


class _Delai(Exception):
    pass


def _sonne(*_):
    raise _Delai()


def _fonction(regle):
    if isinstance(regle, str):  # source Python d'une fonction `predire`, exécutée dans un espace de noms vide
        ns = {"np": np}
        exec(compile(regle, "<regle>", "exec"), ns)  # noqa: S102 — règles candidates, bac à sable par délai
        f = ns["predire"]
        return lambda g, a: np.asarray(f(g.copy(), a), dtype=np.int8)
    return lambda g, a: regle_param(regle, g, a)


def evaluer(regle, delai_s=1):
    """Exactitude case par case (cases gardées), première transition contredite, classe d'erreur dominante."""
    try:
        f = _fonction(regle)
    except Exception as e:  # noqa: BLE001
        return {"regle": regle, "exactitude": 0.0, "premiere_erreur": 0, "classe": f"source invalide : {type(e).__name__}"}
    bonnes = total = 0
    premiere, classes = None, Counter()
    ancien = signal.signal(signal.SIGALRM, _sonne)
    try:
        for i, (g0, a, g1) in enumerate(_T):
            signal.alarm(delai_s)
            try:
                p = f(g0, a)
            except _Delai:
                p, classes["delai"] = g0, classes["delai"] + 1
            except Exception:  # noqa: BLE001
                p, classes["exception"] = g0, classes["exception"] + 1
            finally:
                signal.alarm(0)
            if p.shape != g1.shape:
                p = g0
            juste = (p == g1) | ~_G
            bonnes += int(juste.sum())
            total += juste.size
            if not juste.all():
                if premiere is None:
                    premiere = i
                faux = ~juste
                bouge_vrai, bouge_pred = (g1 != g0) & faux, (p != g0) & faux
                classes["mouvement manqué" if (bouge_vrai & ~bouge_pred).any() and not bouge_pred.any() else
                        "faux mouvement" if bouge_pred.any() and not bouge_vrai.any() else "mauvais résultat"] += 1
    finally:
        signal.signal(signal.SIGALRM, ancien)
    return {"regle": regle, "exactitude": bonnes / max(total, 1), "premiere_erreur": premiere,
            "classe": classes.most_common(1)[0][0] if classes else "aucune"}


def verifier(regles, trans, garde=None, processus=None):
    """Évalue toutes les règles sur toutes les transitions, en parallèle. Rend la liste des résultats (même ordre)."""
    if garde is None:
        garde = masque_de(trans)
    n = processus or max(1, (os.cpu_count() or 2) - 2)
    if n == 1:
        _init(trans, garde)
        return [evaluer(r) for r in regles]
    with Pool(n, initializer=_init, initargs=(trans, garde)) as p:
        return p.map(evaluer, regles, chunksize=max(1, len(regles) // (8 * n)))


def debit(regles, trans, processus):
    t0 = time.perf_counter()
    verifier(regles, trans, processus=processus)
    dt = time.perf_counter() - t0
    return {"processus": processus, "regles": len(regles), "transitions": len(trans), "s": round(dt, 2),
            "regles_par_s": round(len(regles) / dt, 1), "regles_par_s_par_coeur": round(len(regles) / dt / processus, 1)}


# ---------------------------------------------------------------- porte de rejeu exact (CW-065.1-2)

INTERDITS = {"history", "transitions", "last_transition", "current_frame", "previous_frame", "latest_frame", "open", "eval",
             "exec", "compile", "globals", "locals", "vars", "__import__", "getattr", "setattr", "input", "pas", "step",
             "action_num", "t", "tour"}
MAX_LITTERAL = 64     # au-delà, une liste/chaîne littérale ressemble à une table d'images mémorisée


def empreinte_verificateur():
    """sha256 de ce fichier : un résultat de porte n'est valable qu'avec l'empreinte consignée (aucun agent ne modifie le juge)."""
    return hashlib.sha256(_Path(__file__).read_bytes()).hexdigest()


def anti_degenere(source):
    """Rejette les règles dégénérées AVANT toute exécution : lecture de la trace ou de l'historique, compteur de pas,
    table littérale, introspection, `global`. Rend la liste des motifs (vide = acceptable)."""
    try:
        t = ast.parse(source)
    except SyntaxError as e:
        return [f"syntaxe : {e.msg}"]
    defs = [n for n in t.body if isinstance(n, ast.FunctionDef)]
    motifs = []
    if not any(d.name == "predire" for d in defs):
        motifs.append("pas de fonction predire")
    for d in defs:
        if d.name == "predire" and [a.arg for a in d.args.args][:2] != ["grille", "action"] and len(d.args.args) != 2:
            motifs.append("predire doit prendre exactement (grille, action)")
    for n in ast.walk(t):
        if isinstance(n, ast.Name) and n.id in INTERDITS:
            motifs.append(f"nom interdit : {n.id}")
        elif isinstance(n, ast.Attribute) and n.attr.startswith("__"):
            motifs.append(f"introspection : {n.attr}")
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            motifs.append("global/nonlocal")
        elif isinstance(n, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and len(getattr(n, "elts", None) or getattr(n, "keys", [])) > MAX_LITTERAL:
            motifs.append("table littérale trop grande")
        elif isinstance(n, ast.Constant) and isinstance(n.value, (str, bytes)) and len(n.value) > 4 * MAX_LITTERAL:
            motifs.append("chaîne littérale trop grande")
    return sorted(set(motifs))


def porte(regle, trans, garde=None):
    """Porte stricte : la règle doit rejouer TOUTES les transitions exactement (garde=None : pixel pour pixel, HUD compris).
    Rend {accepte, motif, premiere_erreur, exactitude, empreinte}."""
    if isinstance(regle, str):
        motifs = anti_degenere(regle)
        if motifs:
            return {"accepte": False, "motif": "dégénérée : " + ", ".join(motifs), "premiere_erreur": None,
                    "exactitude": None, "empreinte": empreinte_verificateur()}
    g = np.ones(trans[0][0].shape, dtype=bool) if garde is None else garde
    _init(trans, g)
    r = evaluer(regle)
    ok = r["exactitude"] == 1.0 and r["premiere_erreur"] is None
    return {"accepte": ok, "motif": "rejeu exact" if ok else f"contredite ({r['classe']})", "premiere_erreur": r["premiere_erreur"],
            "exactitude": r["exactitude"], "empreinte": empreinte_verificateur()}


def muter(trans, graine=0):
    """Un défaut planté : une transition de la trace modifiée (1 pixel du résultat changé, ou action remplacée)."""
    rng = _random.Random(graine)
    t = list(trans)
    i = rng.randrange(len(t))
    g0, a, g1 = t[i]
    if rng.random() < 0.5:
        g1 = g1.copy()
        y, x = rng.randrange(g1.shape[0]), rng.randrange(g1.shape[1])
        g1[y, x] = (int(g1[y, x]) + 1 + rng.randrange(14)) % 16
        genre = "pixel"
    else:
        autres = [b for b in (("UP", None, None), ("DOWN", None, None), ("LEFT", None, None), ("RIGHT", None, None)) if b != a]
        a, genre = rng.choice(autres), "action"
    t[i] = (g0, a, g1)
    return t, (i, genre)


def tester_le_testeur(regle, trans, n=20):
    """La porte doit ACCEPTER la règle sur la vraie trace et la REJETER sur chaque trace mutée (sauf mutation sans effet
    sur la prédiction : une action remplacée par une action de même effet). Rend la part de défauts détectés."""
    if not porte(regle, trans)["accepte"]:
        return {"valide": False, "raison": "la règle ne passe pas la vraie trace", "detectes": 0, "plantes": 0}
    detectes, plantes = 0, 0
    f = _fonction(regle)
    for k in range(n):
        tm, (i, genre) = muter(trans, k)
        g0, a, _g1 = tm[i]
        if genre == "action" and np.array_equal(f(g0, a), trans[i][2]):
            continue  # mutation neutre pour cette règle : rien à détecter
        plantes += 1
        detectes += not porte(regle, tm)["accepte"]
    return {"valide": detectes == plantes, "detectes": detectes, "plantes": plantes}
