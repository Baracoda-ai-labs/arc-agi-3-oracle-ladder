# SPDX-License-Identifier: MIT-0
"""C (CW-315) — transformer un refus de rejeu en corrections, sans réapprendre tout le jeu.

`diagnostiquer(th, tr)` : 1re transition qui diverge, objets en cause (prédits sans être vus, vus sans être prédits),
cases fausses, lois de la théorie qui touchent ces classes, corrections compatibles avec CETTE transition.
`corriger(th, tr)` : boucle bornée contre-exemple → correction → rejeu de tout l'historique → garder si le rejeu
s'améliore STRICTEMENT, sinon rejeter ; s'arrête dès qu'aucune correction n'aide. Aucun savoir propre à un jeu."""
from copy import deepcopy

import numpy as np

from chrysalide.arc3.logique.theorie import rejeu


def _cases_fausses(th, tr, t):
    pred, _ = th.pas(tr.etats[t], tr.actions[t], tr.taille)
    rd = np.asarray(th.rendu(pred, tr.taille, tr.fond))
    vu = np.asarray(tr.cases[t + 1])
    masque = np.zeros(vu.shape, bool)
    for r, c in getattr(tr, "exclues", ()):
        if 0 <= r < masque.shape[0] and 0 <= c < masque.shape[1]:
            masque[r, c] = True
    if rd.shape != vu.shape:
        return pred, None
    return pred, [(int(x), int(y)) for y, x in zip(*np.nonzero((rd != vu) & ~masque), strict=True)]


def _deplacement(e0, e1, c):
    """Pas commun des objets de classe c entre deux états (même forme, plus proche), ou None s'il n'est pas unique."""
    pas = set()
    for o in (o for o in e0 if o[0] == c):
        cands = [p for p in e1 if p[0] == c and p[1] == o[1]]
        if not cands:
            return None
        p = min(cands, key=lambda p: abs(p[2] - o[2]) + abs(p[3] - o[3]))
        pas.add((p[2] - o[2], p[3] - o[3]))
    return next(iter(pas)) if len(pas) == 1 else None


def lois_de(th, classes):
    """Faits de la théorie qui mentionnent une des classes."""
    out = [f"move(c{c},a{a},{d[0]},{d[1]})" for (c, a), d in th.moves.items() if c in classes]
    out += [f"solide(c{c})" for c in th.solides if c in classes]
    out += [f"poussable(c{c})" for c in th.poussables if c in classes]
    out += [f"poursuit(c{c},c{v})" for c, v in th.autonomes.items() if c in classes or v in classes]
    if th.porteur and (th.porteur[0] in classes or any(h in classes for h, _ in th.hotes)):
        out.append(f"porteur(c{th.porteur[0]},a{th.porteur[1]})")
    return out


def diagnostiquer(th, tr):
    """→ None si tout rejoue, sinon le diagnostic de la 1re transition fausse (dictionnaire)."""
    th.hors_jeu = tr.exclues
    for t, a in enumerate(tr.actions):
        pred, fausses = _cases_fausses(th, tr, t)
        if fausses == []:
            continue
        vu = tr.etats[t + 1]
        predits, vus = set(pred), set(vu)
        en_trop, manquants = sorted(predits - vus), sorted(vus - predits)
        classes = sorted({o[0] for o in en_trop} | {o[0] for o in manquants})
        corrections = []
        w, h = tr.taille
        bord = next((b for b in ((lambda x, y, h=h: y == h - 1), (lambda x, y: y == 0), (lambda x, y, w=w: x == w - 1),
                                  (lambda x, y: x == 0)) if fausses and all(b(x, y) for x, y in fausses)), None)
        if bord is not None:  # compteur sur un bord de la grille (jauge, HUD) : toute sa ligne de bord est masquée,
            from chrysalide.arc3.logique.theorie import cells  # cases des objets qui la touchent (elle recule à chaque coup)
            touches = [o for o in (*tr.etats[t], *pred) if any(bord(x, y) for x, y in cells(o))]
            ligne = {(x, y) for o in touches for x, y in cells(o) if bord(x, y)} | set(fausses)
            corrections.append(("masquer", tuple(sorted(ligne))))
        for c in classes:
            d = _deplacement(tr.etats[t], vu, c)
            if d is not None and not isinstance(a, tuple) and th.moves.get((c, a), (0, 0)) != d:
                corrections.append(("move", c, a, d))
            if c in th.autonomes:
                corrections.append(("sans_poursuite", c))
            if c in th.poussables:
                corrections.append(("non_poussable", c))
            if c in th.solides:
                corrections.append(("non_solide", c))
        moves = [c for c in corrections if c[0] == "move"]
        if len(moves) >= 2:  # m0r0 N6 : deux blocs miroirs, chaque pas seul n'améliore rien ; ensemble, si
            corrections.append(("ensemble", tuple(moves)))
        return {"t": t, "action": a, "cases_fausses": fausses if fausses is not None else "taille",
                "en_trop": [(o[0], o[2], o[3], len(o[1])) for o in en_trop],
                "manquants": [(o[0], o[2], o[3], len(o[1])) for o in manquants],
                "classes": classes, "lois": lois_de(th, set(classes)), "corrections": corrections}
    return None


def appliquer(th, corr):
    """Copie de la théorie avec une correction appliquée."""
    if corr[0] == "ensemble":
        for c in corr[1]:
            th = appliquer(th, c)
        return th
    t2 = deepcopy(th)
    if corr[0] == "move":
        _, c, a, d = corr
        if d == (0, 0):
            t2.moves.pop((c, a), None)
        else:
            t2.moves[(c, a)] = d
        t2.moves_supposes.pop((c, a), None)
    elif corr[0] == "sans_poursuite":
        t2.autonomes = {k: v for k, v in t2.autonomes.items() if k != corr[1]}
    elif corr[0] == "non_poussable":
        t2.poussables = frozenset(t2.poussables - {corr[1]})
    elif corr[0] == "non_solide":
        t2.solides = frozenset(t2.solides - {corr[1]})
    return t2


def _masquee(tr, cases):
    """Copie légère de la trajectoire dont le masque d'interface s'étend aux cases (x, y) données (rangées (y, x))."""
    from copy import copy
    t2 = copy(tr)
    t2.exclues = frozenset(tr.exclues) | {(y, x) for x, y in cases}
    return t2


def corriger(th, tr, max_tours=8):
    """Boucle bornée. → (théorie, trajectoire au masque éventuellement étendu, journal) ; journal = [(diagnostic résumé,
    correction gardée, rejeu avant, après)]. « masquer » étend le masque de la TRAJECTOIRE (perception), pas la théorie."""
    th.hors_jeu = tr.exclues
    ok0 = rejeu(th, tr)[0]
    journal = []
    for _ in range(max_tours):
        dg = diagnostiquer(th, tr)
        if dg is None:
            break
        meilleur = None
        for corr in dg["corrections"]:
            t2, tr2 = (th, _masquee(tr, corr[1])) if corr[0] == "masquer" else (appliquer(th, corr), tr)
            t2.hors_jeu = tr2.exclues
            ok = rejeu(t2, tr2)[0]
            if ok > ok0 and (meilleur is None or ok > meilleur[0]):
                meilleur = (ok, corr, t2, tr2)
        if meilleur is None:
            journal.append(({"t": dg["t"], "classes": dg["classes"]}, None, ok0, ok0))
            break
        journal.append(({"t": dg["t"], "classes": dg["classes"]}, meilleur[1], ok0, meilleur[0]))
        ok0, th, tr = meilleur[0], meilleur[2], meilleur[3]
    return th, tr, journal




def contradictions(tr):
    """C (CW-316) : test de DÉTERMINISME sur une trajectoire. Paires (même état perçu, même action) → états suivants
    différents : une INFORMATION manque à l'état (compteur, phase, identité, détail effacé), aucune règle sur cet état ne
    peut expliquer les deux. → [{action, t (occurrences), brut_identique, objets qui diffèrent}] ; `brut_identique` : les
    images de départ sont identiques aussi au pixel (sinon la perception a fusionné deux scènes différentes)."""
    vus = {}
    for t, a in enumerate(tr.actions):
        if isinstance(a, tuple):
            a = ("clic", a[1], a[2])
        vus.setdefault((frozenset(tr.etats[t]), a), []).append(t)
    out = []
    for (_, a), ts in vus.items():
        suites = {frozenset(tr.etats[t + 1]) for t in ts}
        if len(suites) < 2:
            continue
        t0, t1 = ts[0], next(t for t in ts[1:] if frozenset(tr.etats[t + 1]) != frozenset(tr.etats[ts[0] + 1]))
        brut = bool(np.array_equal(np.asarray(tr.cases[t0]), np.asarray(tr.cases[t1])))
        diff = sorted({o[0] for o in set(tr.etats[t0 + 1]) ^ set(tr.etats[t1 + 1])})
        out.append({"action": a, "t": ts, "brut_identique": brut, "classes_qui_different": diff})
    return out


__all__ = ["appliquer", "contradictions", "corriger", "diagnostiquer", "lois_de"]
