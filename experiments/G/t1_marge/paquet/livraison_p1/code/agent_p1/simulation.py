"""Rejeu exact d'un programme d'objet sur les transitions enregistrées ; erreurs typées.

Prédiction à un pas (la pose observée resynchronise la pose interne quand l'objet est visible) :
une erreur unique ne se propage pas en cascade, chaque transition est jugée séparément.
Catégories : transition (pose fausse, apparition/disparition non prédite hors occlusion possible),
rendu (objet prédit sous le joueur ou sous une porte fermée mais non vu), perception (lecture impossible).
"""
from .semantique import pas_objet, visible, etat_initial, INDETERMINE


def contexte(L, model, origine, portes_avant):
    return dict(action=L['action'], effectif=L['effectif'], joueur_avant=L['joueur_avant'],
                joueur_apres=L['joueur_apres'], pas=model.step, noeuds=model.node_set, origine=origine,
                portes_fermees_avant=portes_avant, portes_fermees_apres=set(map(tuple, L['portes_fermees'])))


def _sous_joueur(pos, joueur, model):
    if pos is None or joueur is None:
        return False
    return abs(pos[0] - joueur[0]) < model.width and abs(pos[1] - joueur[1]) < model.height


def simuler(prog, objet, lignes, model, portes_initiales=()):
    """Rend (predictions, erreurs, non_predits, explique). predictions[i] = pose visible prédite ou None/INDETERMINE."""
    origine = objet['pos0']
    s = etat_initial(origine); portes_avant = set(map(tuple, portes_initiales))
    preds, erreurs, nonp, expl = [], [], [], []
    for L in lignes:
        oid = objet['id']; p0, p1 = L['objets'][oid]
        ctx = contexte(L, model, origine, portes_avant)
        ns = pas_objet(prog, s, ctx)
        if ns == INDETERMINE:
            preds.append(INDETERMINE); nonp.append(L['t'])
            # resynchronisation sur l'observation pour continuer le jugement des pas suivants
            s = (p1, s[1] + 1, p1 is not None, s[3], s[4]) if p1 is not None else s
        else:
            v = visible(prog, ns, ctx); preds.append(v)
            if v == p1:
                expl.append(L['t'])
            else:
                if p1 is None and (_sous_joueur(v, L['joueur_apres'], model)):
                    cat = 'rendu'
                else:
                    cat = 'transition'
                erreurs.append((L['t'], cat, v, p1))
            s = ns
            if p1 is not None and ns[0] != p1:
                d = ns[3]
                s = (p1, ns[1], True, d, ns[4])
        portes_avant = ctx['portes_fermees_apres']
    return preds, erreurs, nonp, expl


def etat_final(prog, objet, lignes, model, portes_initiales=()):
    """État interne de l'objet après rejeu (avec resynchronisation sur les poses observées)."""
    s = etat_initial(objet['pos0']); portes_avant = set(map(tuple, portes_initiales))
    for L in lignes:
        p0, p1 = L['objets'][objet['id']]
        ctx = contexte(L, model, objet['pos0'], portes_avant)
        ns = pas_objet(prog, s, ctx)
        if ns == INDETERMINE:
            ns = (p1 if p1 is not None else s[0], s[1] + 1, p1 is not None or s[2], s[3], s[4])
        if p1 is not None and ns[0] != p1:
            ns = (p1, ns[1], True, ns[3], ns[4])
        if p1 is not None and not ns[2]:
            ns = (p1, ns[1], True, ns[3], ns[4])
        s = ns; portes_avant = ctx['portes_fermees_apres']
    return s


def induire_route(objet, lignes):
    """Route latente induite : poses successives après chaque déplacement, par vie (segments entre ACTION5).
    Rend (route, incoherences) ; une incohérence = deux vies qui divergent sur un même rang."""
    oid = objet['id']; vies = [[objet['pos0']]]
    for L in lignes:
        p0, p1 = L['objets'][oid]
        if L['action'] == 5:
            vies.append([objet['pos0']])
            continue
        if p1 is not None and p1 != vies[-1][-1]:
            vies[-1].append(p1)
    route = []; inc = 0
    for k in range(max(map(len, vies))):
        vals = {tuple(v[k]) for v in vies if len(v) > k}
        if len(vals) > 1:
            inc += 1
        route.append(sorted(vals)[0])
    return route, inc
