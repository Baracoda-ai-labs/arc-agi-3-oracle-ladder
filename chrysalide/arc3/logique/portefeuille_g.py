# SPDX-License-Identifier: MIT-0
"""[G] CW-429 : PORTEFEUILLE de recherche dans le langage (règles exactes, P0 : 15/60 pour chaque bras seul à 60 s,
18/60 pour le portefeuille 30 s + 30 s, CCM-054-G), pour le moteur, derrière `CHRYS_PORTEFEUILLE_G=1` (éteint).
Deux bras, joués à la suite sur le même budget :
  1. `macro_g` (algorithme gelé de `experiments/G/macro_g.py`, gel 2) : macros = largeur aux flèches, un état par position
     nouvelle des objets de la signature d'un piloté ; recherche haute en largeur sur macros + coups non fléchés,
     alternance (pas deux macros d'affilée), repli sans alternance si l'espace s'épuise. SEUL ÉCART au gel : l'échéance
     est aussi testée dans les macros (le moteur ne doit jamais dépasser son budget de tour) ;
  2. largeur simple (clé `cle_complete`) : équivalent du `bfs` de la couche 6, seule méthode de la couche 6 qui ait gagné
     sur P0 (15/15).
`portefeuille(texte, scene, etat, coups, secondes)` → (plan : liste de coups du langage, ou None, infos).
Coups : tuples du langage (`("UP", None, None)`, `("CLICK", y, x)`, …). Aucune lecture de fichier, aucun état global."""
import copy
import time
from collections import deque

import numpy as np

FLECHES = ("UP", "DOWN", "LEFT", "RIGHT")
GAGNE = ("niveau", "victoire")


def _sig(o):
    px = np.asarray(o["pixels"])
    return o.get("nom"), tuple(o.get("tags") or ()), tuple(sorted(set(px[px >= 0].ravel().tolist())))


def macro_g(texte, scene, etat, coups, secondes, alterner=True):
    from chrysalide.arc3.logique.plan_langage import cle_complete
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    T, t0 = time.process_time, time.process_time()
    fin = t0 + secondes
    prog = ProgrammeCompile(texte)
    if etat is not None:
        prog.etat = copy.deepcopy(etat)
    e0 = prog.etat
    fleches = [c for c in coups if c[0] in FLECHES]
    autres = [c for c in coups if c[0] not in FLECHES]

    def pas(sc, e, c):
        s2, e2 = cloner(sc, e)
        prog.etat = e2
        try:
            prog.step(s2, c)
        except Exception:  # noqa: BLE001 — coup qui plante : branche abandonnée
            return None, None
        return s2, prog.etat
    pil = set()
    for c in fleches:
        s2, _ = pas(scene, e0, c)
        if s2 is not None and len(s2.sprites) == len(scene.sprites):
            pil |= {i for i, (a, b) in enumerate(zip(scene.sprites, s2.sprites, strict=True)) if (a["x"], a["y"]) != (b["x"], b["y"])}
    signatures = {_sig(scene.sprites[i]) for i in pil}

    def pos(sc):
        return tuple(sorted((o["x"], o["y"], bool(o.get("visible", True))) for o in sc.sprites if _sig(o) in signatures))

    def macros(sc, e):
        vus, file, out = {pos(sc)}, deque([(sc, e, [])]), []
        while file and T() < fin:
            s, ee, ch = file.popleft()
            for c in fleches:
                s2, e2 = pas(s, ee, c)
                if s2 is None:
                    continue
                if s2.issue in GAGNE:
                    return [(s2, e2, [*ch, c], True)]
                if s2.issue is not None:
                    continue
                p = pos(s2)
                if p in vus:
                    continue
                vus.add(p)
                out.append((s2, e2, [*ch, c], False))
                file.append((s2, e2, [*ch, c]))
        return out
    haut, file, plan = {cle_complete(scene, e0)}, deque([(scene, e0, [], False)]), None
    while file and T() < fin and plan is None:
        s, e, ch, apres = file.popleft()
        suiv = [] if (apres and alterner) else [(s2, e2, cs, g, True) for s2, e2, cs, g in macros(s, e)]
        for c in autres:
            s2, e2 = pas(s, e, c)
            if s2 is not None and (s2.issue is None or s2.issue in GAGNE):
                suiv.append((s2, e2, [c], s2.issue is not None, False))
        for s2, e2, cs, gagne, est_macro in suiv:
            if gagne:
                plan = [*ch, *cs]
                break
            k = cle_complete(s2, e2)
            if k in haut:
                continue
            haut.add(k)
            file.append((s2, e2, [*ch, *cs], est_macro))
    inf = {"bras": "macro_g", "etats_hauts": len(haut), "cpu": round(T() - t0, 2), "alterner": alterner}
    if plan is None and not file and alterner and T() < fin:
        p2, i2 = macro_g(texte, scene, etat, coups, fin - T(), alterner=False)
        return p2, {**i2, "repli": "sans alternance"}
    return plan, inf


def largeur(texte, scene, etat, coups, secondes):
    from chrysalide.arc3.logique.plan_langage import cle_complete
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    T, t0 = time.process_time, time.process_time()
    prog = ProgrammeCompile(texte)
    if etat is not None:
        prog.etat = copy.deepcopy(etat)
    e0 = prog.etat
    vus, file = {cle_complete(scene, e0)}, deque([(scene, e0, [])])
    while file and T() - t0 < secondes:
        s, e, ch = file.popleft()
        for c in coups:
            s2, e2 = cloner(s, e)
            prog.etat = e2
            try:
                prog.step(s2, c)
            except Exception:  # noqa: BLE001, S112
                continue
            if s2.issue in GAGNE:
                return [*ch, c], {"bras": "largeur", "etats": len(vus), "cpu": round(T() - t0, 2)}
            if s2.issue is not None:
                continue
            k = cle_complete(s2, prog.etat)
            if k in vus:
                continue
            vus.add(k)
            file.append((s2, prog.etat, [*ch, c]))
    return None, {"bras": "largeur", "etats": len(vus), "cpu": round(T() - t0, 2), "epuise": not file}


def portefeuille(texte, scene, etat, coups, secondes):
    """Moitié du budget pour macro_g, le reste pour la largeur. → (plan | None, infos des bras joués)."""
    t0 = time.process_time()
    plan, i1 = macro_g(texte, scene, etat, coups, secondes / 2)
    if plan is not None:
        return plan, {"gagnant": "macro_g", "bras": [i1]}
    plan, i2 = largeur(texte, scene, etat, coups, max(0.5, secondes - (time.process_time() - t0)))
    return plan, {"gagnant": "largeur" if plan is not None else None, "bras": [i1, i2]}
