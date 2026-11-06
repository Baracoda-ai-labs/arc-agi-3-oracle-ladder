# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — `verifier_loi` (CCM-102-B, lot 3 « choix fermé ») : la porte d'une loi candidate proposée en mots de
l'ontologie. On ajoute (ou retire) la loi à la théorie, puis on compte les transitions du niveau que la théorie rejoue
exactement (recalée à chaque pas, comme `rejeu_apprentissage`), avant et après. Aucun accès au jeu.
Lois acceptées (tuples, classes = entiers de la perception de C) :
  ("move", c, a, dx, dy)          le mobile c se déplace de (dx, dy) à l'action a
  ("saut", c, a, dx2, dy2)        si le pas est bloqué, c saute de (dx2, dy2)
  ("teleporte", k, dx, dy)        arriver sur la classe k décale encore de (dx, dy)
  ("teleporte_case", x, y, dx, dy) arriver sur la case (x, y) décale encore de (dx, dy)
  ("solide", c) / ("non_solide", c)   la classe c bloque (ou ne bloque plus)
  ("fond_solide", bool)           on n'entre que sur des cases couvertes par un objet (ou non)
  ("consomme", c1, c2)            c1 qui recouvre c2 le retire
  ("transforme", m, c, c2)        un mobile qui arrive sur m change les objets c en c2
  ("poussable", c)                c est poussé par le mobile"""
from dataclasses import replace

from chrysalide.arc3.logique.induction import precedent_pile


def appliquer(th, loi):
    k, *p = loi
    if k == "move":
        return replace(th, moves={**th.moves, (p[0], p[1]): (p[2], p[3])})
    if k == "saut":
        return replace(th, saut={**th.saut, (p[0], p[1]): (p[2], p[3])})
    if k == "teleporte":
        return replace(th, teleports={**th.teleports, p[0]: (p[1], p[2])})
    if k == "teleporte_case":
        return replace(th, teleports_cases={**th.teleports_cases, (p[0], p[1]): (p[2], p[3])})
    if k == "solide":
        return replace(th, solides=th.solides | {p[0]})
    if k == "non_solide":
        return replace(th, solides=th.solides - {p[0]}, murs_supposes=th.murs_supposes - {p[0]})
    if k == "fond_solide":
        return replace(th, fond_solide=bool(p[0]))
    if k == "consomme":
        return replace(th, consomme=th.consomme | {(p[0], p[1])})
    if k == "transforme":
        return replace(th, transforme=th.transforme | {(p[0], p[1], p[2])})
    if k == "poussable":
        return replace(th, poussables=th.poussables | {p[0]})
    raise ValueError(f"loi inconnue : {k}")


def expliquees(th, sources):
    """→ (transitions rejouées exactement, total, liste des t non expliqués par source)."""
    ok = n = 0
    rates = []
    for s in sources:
        tr, ts = (s[0], s[1]) if isinstance(s, tuple) else (s, None)
        th2 = replace(th, hors_jeu=getattr(tr, "exclues", th.hors_jeu))
        r = []
        for t in (range(len(tr.actions)) if ts is None else ts):
            n += 1
            bon = th2.pas(tr.etats[t], tr.actions[t], tr.taille,
                          precedent=precedent_pile(tr.etats, tr.actions, t, th2.annule))[0] == tr.etats[t + 1]
            ok += bon
            if not bon:
                r.append(t)
        rates.append(r)
    return ok, n, rates


def verifier_loi(th, loi, sources):
    """→ {"avant": (ok, n), "apres": (ok, n), "gagnees": [t…], "perdues": [t…], "accepte": apres > avant et rien perdu}.
    `sources` : trajectoires (faits.Trajectoire, temps.TrajTemps…) ou tuples (tr, ts, …) comme pour `induire`."""
    a, n, ra = expliquees(th, sources)
    b, _, rb = expliquees(appliquer(th, loi), sources)
    gagnees = sorted({(i, t) for i, r in enumerate(ra) for t in r} - {(i, t) for i, r in enumerate(rb) for t in r})
    perdues = sorted({(i, t) for i, r in enumerate(rb) for t in r} - {(i, t) for i, r in enumerate(ra) for t in r})
    return {"loi": loi, "avant": (a, n), "apres": (b, n), "gagnees": gagnees, "perdues": perdues,
            "accepte": b > a and not perdues}
