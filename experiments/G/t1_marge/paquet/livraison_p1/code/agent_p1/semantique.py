"""Sémantique unique des programmes d'objet (utilisée par la simulation sur traces ET par le modèle de planification).

État d'objet (hachable) : (pos, ptr, vivant, dir, en_attente).  Ordre d'un coup : le joueur bouge, puis l'objet,
puis l'état des portes est évalué (la porte fermée APRÈS le coup décide écrasement / occultation).
Une prédiction impossible à faire (choix non déterminé par le programme) rend INDETERMINE.
"""
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
TRANSFO = {
    'id': lambda dx, dy: (dx, dy), 'flipx': lambda dx, dy: (-dx, dy), 'flipy': lambda dx, dy: (dx, -dy),
    'rot90': lambda dx, dy: (-dy, dx), 'rot180': lambda dx, dy: (-dx, -dy), 'rot270': lambda dx, dy: (dy, -dx),
    'transpose': lambda dx, dy: (dy, dx), 'antitranspose': lambda dx, dy: (-dy, -dx),
}
INDETERMINE = 'indetermine'


def etat_initial(origine):
    return (tuple(origine), 0, True, None, False)


def _sgn(v):
    return (v > 0) - (v < 0)


def _libre(q, ctx, prog):
    if q not in ctx['noeuds']:
        return False
    if prog['destruction'] in ('bloque_par_porte', 'bloque_et_ecrase') and q in ctx['portes_fermees_avant']:
        return False
    return True


def _couloir(pos, d, ctx, prog):
    step = ctx['pas']
    voisins = [(dd, (pos[0] + dd[0] * step, pos[1] + dd[1] * step)) for dd in DIRS.values()]
    libres = [(dd, q) for dd, q in voisins if _libre(q, ctx, prog)]
    if d is not None:
        devant = (pos[0] + d[0] * step, pos[1] + d[1] * step)
        if _libre(devant, ctx, prog):
            return devant, d
        arriere = [(dd, q) for dd, q in libres if dd == (-d[0], -d[1])]
        libres = [(dd, q) for dd, q in libres if dd != (-d[0], -d[1])]
        if not libres and arriere and prog.get('fin_couloir') == 'demi_tour':
            return arriere[0][1], arriere[0][0]
    if len(libres) == 1:
        return libres[0][1], libres[0][0]
    if not libres:
        return pos, d
    return INDETERMINE, None


def _poursuite(pos, cible, ctx, prog, signe):
    step = ctx['pas']; dx, dy = cible[0] - pos[0], cible[1] - pos[1]
    axes = [(abs(dx), (signe * _sgn(dx), 0)), (abs(dy), (0, signe * _sgn(dy)))]
    axes.sort(key=lambda t: -t[0])
    for n, (ux, uy) in axes:
        if (ux, uy) == (0, 0):
            continue
        q = (pos[0] + ux * step, pos[1] + uy * step)
        if _libre(q, ctx, prog):
            return q, (ux, uy)
    return pos, None


def declenche(prog, ctx):
    a = ctx['action']; t = prog['declencheur']
    if t == 'jamais':
        return False
    if t == 'tout_coup':
        return True
    if t == 'coup_joueur':
        return a in (1, 2, 3, 4)
    if t == 'coup_effectif':
        return a in (1, 2, 3, 4) and ctx['effectif']
    raise ValueError(t)


def pas_objet(prog, s, ctx):
    """ctx : action, effectif, joueur_avant, joueur_apres, pas, noeuds, origine,
    portes_fermees_avant, portes_fermees_apres. Rend le nouvel état ou INDETERMINE."""
    pos, ptr, vivant, d, attente = s
    a = ctx['action']
    if a == 5 and prog['reinit'] == 'action5':
        return etat_initial(ctx['origine'])
    if not vivant:
        return s
    tir = declenche(prog, ctx)
    if prog['delai']:
        tir, attente = attente, tir
    if tir:
        e = prog['effet']
        if e == 'miroir':
            if a not in DIRS:
                pass
            else:
                dx, dy = TRANSFO[prog['transfo']](*DIRS[a])
                q = (pos[0] + dx * ctx['pas'], pos[1] + dy * ctx['pas'])
                if _libre(q, ctx, prog):
                    pos, d = q, (dx, dy)
        elif e == 'route_latente':
            ptr += 1; r = prog['route']
            if ptr < len(r):
                q = r[ptr]; d = (_sgn(q[0] - pos[0]), _sgn(q[1] - pos[1])); pos = q
            elif prog['fin_route'] == 'disparait':
                vivant = False
            elif prog['fin_route'] == 'couloir':
                q, nd = _couloir(pos, d, ctx, prog)
                if q == INDETERMINE:
                    return INDETERMINE
                pos, d = q, nd
        elif e == 'couloir':
            q, nd = _couloir(pos, d, ctx, prog)
            if q == INDETERMINE:
                return INDETERMINE
            pos, d = q, nd; ptr += 1
        elif e in ('poursuite', 'fuite'):
            pos, nd = _poursuite(pos, ctx['joueur_apres'], ctx, prog, 1 if e == 'poursuite' else -1)
            d = nd or d
    if prog['destruction'] in ('porte_fermee', 'bloque_et_ecrase') and pos in ctx['portes_fermees_apres']:
        vivant = False
    return (pos, ptr, vivant, d, attente)


def visible(prog, s, ctx):
    pos, ptr, vivant, d, attente = s
    if not vivant:
        return None
    if prog['destruction'] == 'occultation_porte' and pos in ctx['portes_fermees_apres']:
        return None
    return pos
