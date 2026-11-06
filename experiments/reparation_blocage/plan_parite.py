"""Recherche conditionnelle GF(2), sans droit d'action ni règle par jeu.

Actions au format Theorie.pas : tuples (code, x, y), coordonnées du modèle.
Le plan retourné doit être converti par l'appelant puis vérifié dans Chaine.
"""
import copy
from dataclasses import fields
from chrysalide.arc3.logique.theorie import (
    Theorie, VOISINS8, cells, centres_motifs, roles_motif, sous_clic_formes,
)


def resoudre(equations, variables):
    """Une solution binaire ; variables libres à zéro, sans optimalité de longueur."""
    pivots = {}
    for masque, valeur in equations:
        while masque:
            pivot = masque.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = (masque, valeur)
                break
            m, v = pivots[pivot]
            masque ^= m
            valeur ^= v
        if not masque and valeur:
            return None
    solution = 0
    for pivot in sorted(pivots):
        masque, valeur = pivots[pivot]
        if ((masque & solution).bit_count() & 1) != valeur:
            solution |= 1 << pivot
    assert solution < 1 << variables
    return solution


def proposer(theorie, monde, actions, taille, but=None):
    """Retourne (plan de tuples Theorie, diagnostic) ; None = refus ou UNSAT local."""
    diag = {'droit_action': False, 'portee': 'modele_conditionnel',
            'verification_chaine_requise': True, 'optimalite': False}
    def refus(raison):
        return None, {**diag, 'statut': 'hors_contrat', 'raison': raison}
    if type(theorie) is not Theorie:
        return refus('type_theorie_non_standard')
    th = copy.deepcopy(theorie)
    # Pour un clic pur : hors_jeu ne filtre pas clic(), et formes ne sert
    # qu'à transforme (refusé). Le fallback motif dépend uniquement de géométrie.
    permis = {'bascule', 'motif', 'motif_formes', 'formes_bascule', 'hitbox_formes',
              'formes', 'hors_jeu',
              'but', 'buts_motifs', 'buts_compatibles', 'obligations'}
    defaut = Theorie()
    for f in fields(th):
        if f.name not in permis and getattr(th, f.name) != getattr(defaut, f.name):
            return refus('mecanisme_non_admis:' + f.name)
    if set(vars(th)) - {f.name for f in fields(th)}:
        return refus('etat_dynamique_non_declare')
    but = th.but if but is None else but
    if not but or but[0] != 'motif_rel' or not (th.motif_formes or th.motif):
        return refus('but_ou_motif_non_admis')
    cycle = sorted(th.bascule)
    if len(cycle) != 2 or any(th.bascule[k] != cycle[1-i] for i, k in enumerate(cycle)):
        return refus('bascule_pas_un_unique_cycle_binaire')
    try:
        roles = roles_motif(*but[1:])
    except (ValueError, TypeError):
        return refus('roles_du_but_invalides')
    if set(cycle) & set(roles):
        return refus('marques_de_but_non_statiques')
    monde = tuple(monde)
    def identite(o):
        return o[1], o[2], o[3]
    objets = {identite(o): o for o in monde}
    if len(objets) != len(monde) or any(not o[1] for o in monde):
        return refus('identites_ambigues_ou_virtuelles')
    col, proprietaire = {}, {}
    for cle, o in objets.items():
        for p in cells(o):
            if p in col:
                return refus('recouvrement_objets')
            col[p], proprietaire[p] = o[0], cle
    actions = list(dict.fromkeys(tuple(a) for a in actions))
    effets = {k: 0 for k in objets}
    for i, action in enumerate(actions):
        if len(action) != 3:
            return refus('action_pas_un_clic_modele')
        touches = [o for o in monde if sous_clic_formes(o, action[1], action[2], th.hitbox_formes)]
        if len(touches) > 1:
            return refus('hitboxes_ambigues_ordre_dependant')
        apres, _ = th.pas(monde, action, taille)
        suivants = {identite(o): o for o in apres}
        if suivants.keys() != objets.keys():
            return refus('geometrie_modifiee')
        for cle, o in objets.items():
            couleur = suivants[cle][0]
            if couleur != o[0]:
                if o[0] not in cycle or couleur != th.bascule[o[0]]:
                    return refus('effet_non_binaire')
                effets[cle] |= 1 << i
        retour, _ = th.pas(apres, action, taille)
        if set(retour) != set(monde):
            return refus('action_non_involutive')
    centres = centres_motifs(col, set(roles))
    if not centres:
        return refus('aucun_centre')
    equations = []
    for z in centres:
        for dx, dy in VOISINS8:
            role = roles[col[z[0]+dx, z[1]+dy]]
            if role == 'neutre':
                continue
            q = (z[0]+4*dx, z[1]+4*dy)
            if q not in col:
                equations.append((0, 1))
                continue
            cz, cq = col[z], col[q]
            attendu_diff = int(role == 'autre')
            if cz in cycle and cq in cycle:
                equations.append((effets[proprietaire[z]] ^ effets[proprietaire[q]],
                                  int(cz != cq) ^ attendu_diff))
            else:
                # Une couleur hors cycle est statique et jamais égale au cycle.
                equations.append((0, int(cz != cq) ^ attendu_diff))
    solution = resoudre(equations, len(actions))
    diag.update(actions=len(actions), equations=len(equations), centres=len(centres))
    if solution is None:
        return None, {**diag, 'statut': 'insatisfiable_dans_contrat'}
    plan = [a for i, a in enumerate(actions) if solution & (1 << i)]
    fin = monde
    for a in plan:
        fin, _ = th.pas(fin, a, taille)
    if not Theorie._vrai(but, fin):
        return refus('verification_theorie_echouee')
    return plan, {**diag, 'statut': 'plan_modele_non_valide_dans_chaine',
                  'longueur': len(plan), 'theorie_verifiee': True}


def proposer_chaine(chaine):
    """Backend conditionnel ; seule adopter_plan accorde une validation simulée."""
    from chrysalide.arc3.moteur import _clics_offerts, _lot_c
    vue = chaine.perception
    th, tr = getattr(vue, 'th_releve', None), getattr(vue, 'tr', None)
    if th is None or tr is None or not chaine.grilles:
        return {'statut': 'parite_hors_contrat', 'raison': 'theorie_ou_etat_absent'}
    tr = copy.copy(tr)
    tr.etats = list(tr.etats[:len(chaine.grilles)])
    tr.etats += [tr.etat(g) for g in chaine.grilles[len(tr.etats):]]
    autorisees = {tuple(a) for a in chaine.actions}
    actions, traductions = [], {}
    for a in _clics_offerts(th, tr):
        lot = _lot_c(a, tr)
        if lot['action'] != 'MOUSE':
            continue
        sdk = ('MOUSE', lot['row'], lot['col'])
        if sdk in autorisees:
            actions.append(a)
            traductions[a] = sdk
    plan, diag = proposer(th, tr.etats[-1], actions, tr.taille)
    if plan is None or not plan:
        return {'statut': 'parite_sans_plan_actionnable', 'infos': diag}
    # Ne pas préremplir _verifie : conserver le rejeu et contrôle indépendant.
    resultat = chaine.adopter_plan([traductions[a] for a in plan], origine='parite_conditionnelle')
    resultat['infos'] = diag
    return resultat
