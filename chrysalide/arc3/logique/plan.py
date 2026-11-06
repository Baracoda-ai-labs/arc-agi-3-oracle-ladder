# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — planification par BFS dans le modèle induit (0 action réelle) : plus court chemin vers un monde où
le but induit est vrai, en évitant les mondes où la mort induite est vraie. L'état du BFS ne contient que les objets
dynamiques ; le décor statique (murs, sorties…) est mis à part une fois pour toutes. `profondeur` = borne (budget de pas)."""
import contextvars
import heapq
import itertools
import os
import time
from collections import deque

from chrysalide.arc3.logique.theorie import cells

# F (CW-468, autopsie des interventions T1) : 21 échecs sur 36 viennent d'un plan qui fait SORTIR l'objet du terrain
# (bord ou panneau jamais heurtés dans la fenêtre : la théorie ne sait pas qu'ils bloquent). CHRYS_F_ZONE=1 : une
# position où un objet dynamique sort de la boîte des cases où l'on a déjà VU un changement est traitée comme bloquée
# (hypothèse prudente « monde fermé » sur ce qui n'a jamais été observé). Éteint = inchangé. Jeux à clic : sans effet.
_ZONE = contextvars.ContextVar("zone_observee", default=None)


def poser_zone(etats):
    """Boîte (x0, x1, y0, y1), en cases, de tout ce qui a changé entre deux états successifs de la trajectoire."""
    if os.environ.get("CHRYS_F_ZONE") != "1":
        return
    xs, ys = [], []
    for a, b in itertools.pairwise(etats):
        sa, sb = set(a), set(b)
        for o in sa ^ sb:
            for x, y in cells(o):
                xs.append(x)
                ys.append(y)
    _ZONE.set((min(xs), max(xs), min(ys), max(ys)) if xs else None)


def _hors_zone(dyn, zone):
    x0, x1, y0, y1 = zone
    return any(not (x0 <= x <= x1 and y0 <= y <= y1) for o in dyn for x, y in cells(o))


def distance_but(th, monde):
    """Distance au but induit (CW-213, comme `plan_langage.distance_but` mais sur la théorie de C) : sortie/ancre/
    sortie_si = distance (cases) du mobile à la cible la plus proche (+1 si la condition de sortie_si manque) ;
    remplir = cibles non couvertes ; absent = objets restants ; sinon 0. Admissible pour des pas d'une case."""
    if th.but is None:
        return 0
    k, *p = th.but
    par = {}
    for o in monde:
        par.setdefault(o[0], []).append(o)
    if k in ("sortie", "ancre", "sortie_si"):
        m, c = p[0], p[1]
        a, b = [x for o in par.get(m, []) for x in cells(o)], [x for o in par.get(c, []) for x in cells(o)]
        d = min((abs(x[0] - y[0]) + abs(x[1] - y[1]) for x in a for y in b), default=0)
        return d + (1 if k == "sortie_si" and p[2] not in par else 0)
    if k == "remplir":
        couverts = {x for o in par.get(p[0], []) for x in cells(o)}
        return sum(1 for o in par.get(p[1], []) if not cells(o) & couverts)
    if k == "absent":
        return len(par.get(p[0], []))
    if k == "motif_rel":
        from chrysalide.arc3.logique.theorie import motif_ecarts
        return motif_ecarts(monde, p[0], p[1]) or 0
    if k == "copie":
        from chrysalide.arc3.logique.theorie import copie_ecarts
        return copie_ecarts(monde, p[0])
    if k == "marques":  # marques non couvertes, chacune pondérée par sa distance à la pièce la plus proche
        col = (lambda v: (v % 16 if v >= 16 else v) if v >= 0 else None) if p[1] == "couleur" else (lambda v: None)
        pieces = [(c, col(o[0])) for o in monde if len(o[1]) > 1 and o[0] < 512 for c in cells(o)]
        couvert = set(pieces)
        cases = {z for z, _ in pieces}  # marque de couleur inconnue (cachée, -1) : n'importe quelle pièce la couvre
        return sum(1 + min((abs(x - u) + abs(y - v) for (u, v), q in pieces if col(k) is None or q == col(k)), default=0)
                   for k, cs in p[0] for x, y in cs
                   if ((x, y) not in cases if col(k) is None else ((x, y), col(k)) not in couvert))
    return 0


def impasse(th, monde, taille, fixe):
    """C (CW-249, action 2 ; CHRYS_IMPASSES=1) : impasse « coin de Sokoban », générique. Vraie si un objet POUSSABLE sans
    mouvement propre, de la classe que le but doit amener sur ses cibles (remplir / sortie / ancre), hors de toute cible,
    est bloqué (bord ou décor solide) sur un côté horizontal ET un côté vertical : aucune poussée ne l'en sortira."""
    if th.but is None or th.but[0] not in ("remplir", "sortie", "ancre"):
        return False
    p, cible = th.but[1], th.but[2]
    if p not in th.poussables or any(c == p for c, _ in th.moves):
        return False
    w, h = taille
    cibles = {c for o in monde if o[0] == cible for c in cells(o)} | {c for c, k in (fixe or {}).items() if cible in k}

    def bloque(x, y):
        return not (0 <= x < w and 0 <= y < h) or bool(fixe and fixe.get((x, y), frozenset()) & th.solides)
    for o in monde:
        if o[0] != p:
            continue
        cs = cells(o)
        if cs & cibles:
            continue
        cote = {d: all(bloque(x + d[0], y + d[1]) for x, y in cs if (x + d[0], y + d[1]) not in cs)
                for d in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        if (cote[(1, 0)] or cote[(-1, 0)]) and (cote[(0, 1)] or cote[(0, -1)]):
            return True
    return False


def planifier(th, monde, taille, actions, limite=300000, profondeur=None, guide=False, deadline=None):
    """Renvoie (liste d'actions | None, n mondes explorés). `guide=True` : A* sur `distance_but` (CW-213) au lieu de la
    largeur ; mêmes états, même but, même mort."""
    if th.but is None:
        return None, 0
    guide = guide or th.but[0] in ("marques", "motif_rel", "copie")  # but à plusieurs pièces : A* sur les marques non couvertes
    if th.motif:  # jeux à clic : le clic dépend de l'objet cliqué, on garde tout le monde dans l'état
        dyn, decor, fixe = monde, (), None
    else:
        dc = th.couleurs_dynamiques()
        dyn = tuple(o for o in monde if o[0] in dc)
        decor = tuple(o for o in monde if o[0] not in dc)
        fixe = {}
        for o in decor:
            for c in cells(o):
                fixe[c] = fixe.get(c, frozenset()) | {o[0]}
    elaguer = os.environ.get("CHRYS_IMPASSES") == "1"
    from chrysalide.arc3.logique.economie_plan import cout as cout_eco
    from chrysalide.arc3.logique.economie_plan import limite as limite_eco
    reserve = limite_eco()  # F (CW-333, CHRYS_ECONOMIE) : None = inchangé
    zone = _ZONE.get() if not th.motif and os.environ.get("CHRYS_F_ZONE") == "1" else None
    parent = {dyn: None}
    prof = {dyn: 0}
    file = deque([dyn])
    tas, rang = [(distance_but(th, dyn + decor), 0, dyn)], 1
    tours = 0
    while (tas if guide else file) and len(parent) < limite:
        tours += 1
        if deadline is not None and tours % 16 == 1 and time.process_time() >= deadline:
            return None, len(parent)
        m = heapq.heappop(tas)[2] if guide else file.popleft()
        if profondeur is not None and prof[m] >= profondeur:
            continue
        for a in actions:
            m2, _ = th.pas(m, a, taille, fixe)
            if m2 in parent:
                continue
            if zone is not None and _hors_zone(m2, zone):  # CHRYS_F_ZONE : jamais vu là → bloqué
                continue
            complet = m2 + decor
            if reserve is not None:  # victoire avant défaite ; position sans réserve et non gagnante : perdue
                if th.atteint(complet):
                    parent[m2] = (m, a)
                    chemin = []
                    while parent[m2] is not None:
                        m2, a2 = parent[m2]
                        chemin.append(a2)
                    return chemin[::-1], len(parent)
                if prof[m] + cout_eco(a) >= reserve:  # réserve à 0 sans victoire : perdue (le coup gagnant, lui, est gratuit)
                    continue
            if th.meurt(complet) or (elaguer and impasse(th, complet, taille, fixe)):
                continue
            parent[m2] = (m, a)
            prof[m2] = prof[m] + (1 if reserve is None else cout_eco(a))
            if th.atteint(complet):
                chemin = []
                while parent[m2] is not None:
                    m2, a2 = parent[m2]
                    chemin.append(a2)
                return chemin[::-1], len(parent)
            if guide:
                heapq.heappush(tas, (prof[m2] + distance_but(th, complet), rang, m2))
                rang += 1
            else:
                file.append(m2)
    return None, len(parent)


def sous_buts(th, monde):
    """Régression de buts (fins-moyens, CW-091) : la classe exigée par le but (mobile transformé, ou indicateur pour
    `sortie_si`) s'obtient par une chaîne de transformations ; chaque maillon impose « atterrir sur le modificateur M ».
    Renvoie la liste des sous-buts (avant le but final), ou None si le but n'exige rien ou si la chaîne est introuvable."""
    if th.but is None or not th.transforme:
        return None
    presentes = {o[0] for o in monde}
    requise = th.but[3] if th.but[0] == "sortie_si" else th.but[1]
    if requise in presentes:
        return []
    aretes = {}
    for m, c, c2 in th.transforme:
        aretes.setdefault(c, []).append((m, c2))
    depart = list(presentes)
    parent = {c: None for c in depart}
    file = deque(depart)
    while file:
        c = file.popleft()
        if c == requise:
            break
        for m, c2 in aretes.get(c, []):
            if c2 not in parent:
                parent[c2] = (c, m)
                file.append(c2)
    if requise not in parent:
        return None
    chaine, c = [], requise
    while parent[c] is not None:
        c0, m = parent[c]
        chaine.append((c0, m))
        c = c0
    # chaque maillon : « la classe obtenue existe » (le mobile change de classe en atterrissant : viser « mobile sur M »
    # ne serait jamais vrai) ; M est nommé pour que pour_but lève H_mur sur le modificateur
    suivant = {c0: c2 for c2, val in parent.items() if val is not None for c0 in [val[0]]}
    buts = []
    for c0, m in reversed(chaine):
        buts.append(("present", suivant[c0], m))
    return buts


def planifier_rebours(th, monde, taille, actions, limite=300000):
    """Plan par régression : chaque sous-but (atterrir sur le modificateur) puis le but, chacun planifié vers l'avant
    depuis l'état prédit à la fin de l'étape précédente. Repli sur le plan direct si la régression ne s'applique pas.
    Renvoie (plan | None, mondes explorés au total, nombre d'étapes)."""
    sb = sous_buts(th, monde)
    if not sb:
        p, n = planifier(th, monde, taille, actions, limite)
        return p, n, 1
    plan, total, w = [], 0, monde
    for b in sb + [th.but]:
        tb = th.pour_but(b) if b != th.but else th
        p, n = planifier(tb, w, taille, actions, limite)
        total += n
        if p is None:
            return None, total, len(sb) + 1
        for a in p:
            w, _ = th.pas(w, a, taille)
        plan += p
    return plan, total, len(sb) + 1
