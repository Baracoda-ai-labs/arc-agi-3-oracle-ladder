"""Intervention sur un support ignoré du but, prédiction physique conservée."""
import copy
import numpy as np
from chrysalide.arc3.exploration import Explorateur
from revision_but_roles import couverture


def contours_adjacents(supports, statiques):
    """Composantes entourant un support, entièrement dans sa frontière proche."""
    def cases(s):
        return {(int(s['x'])+int(x), int(s['y'])+int(y))
                for y,x in np.argwhere(np.asarray(s['pixels']) >= 0)}
    contours = []
    vus = set()
    for support in supports:
        interieur = cases(support)
        if not interieur:
            continue
        voisinage = {(x+dx,y+dy) for x,y in interieur
                     for dx in (-1,0,1) for dy in (-1,0,1)} - interieur
        # Les quatre frontières cardinales doivent être entourées : un voisin
        # ponctuel ou une composante du fond ne devient pas une cible de sonde.
        bord = {(x+dx,y+dy) for x,y in interieur
                for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))} - interieur
        for s in statiques:
            if id(s) in vus:
                continue
            contour = cases(s)
            if contour and bord <= contour <= voisinage:
                restants = set(contour)
                pile = [restants.pop()]
                while pile:
                    x,y = pile.pop()
                    voisins = {(x+dx,y+dy) for dx in (-1,0,1) for dy in (-1,0,1)} & restants
                    restants.difference_update(voisins)
                    pile.extend(voisins)
                if not restants:
                    contours.append(s)
                    vus.add(id(s))
    return contours


def proposer(source, images, actions, offre, episodes=()):
    from chaine_agent_integree import canon
    from transfert_roles import RolesReaffectes
    if type(source.perception) is not RolesReaffectes:
        return None, {'refus': 'perception_non_supportee'}
    if 6 not in offre or source.refute or not getattr(source, 'but_inconnu', False):
        return None, {'refus': 'but_inconnu_admis_et_clic_requis'}
    controle, courant = source.rejouer()
    if courant is None:
        return None, {'refus': 'modele_non_admis', 'controle': controle}
    vue = source.perception
    if not np.array_equal(vue.rendu(courant[1]), vue.vue(images[-1])):
        return None, {'refus': 'etat_non_synchronise'}
    hyp = couverture(vue)
    supports = []
    for h in hyp:
        if not h['non_couverts']:
            continue
        for x, y, w, ht in h['centres']:
            for s in vue.statiques:
                if (s['x'], s['y'], *np.asarray(s['pixels']).shape) == (x, y, ht, w):
                    supports.append(s)
    contours = contours_adjacents(supports, vue.statiques)
    exploration = Explorateur(graine=0)
    for gs, acts in [(images, actions), *[(e['grilles'], e['actions']) for e in episodes]]:
        if len(gs) != len(acts)+1:
            return None, {'refus': 'episode_non_aligne'}
        for avant, a, apres in zip(gs, acts, gs[1:]):
            code = canon(a)
            coup = {'action': code[0]}
            if code[0] == 'MOUSE':
                coup.update(row=code[1], col=code[2])
            exploration.noter(vue.vue(avant), coup, vue.vue(apres))
    g = vue.vue(images[-1])
    candidats = []
    for a in exploration.candidats(g, offre):
        if a['action'] != 'MOUSE' or exploration.essais[(g.tobytes(), exploration._cle(a))]:
            continue
        y, x = a['row'], a['col']
        for s in supports + contours:
            px = np.asarray(s['pixels']); dy, dx = y-s['y'], x-s['x']
            if (0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] and
                    px[dy,dx] >= 0 and g[y,x] == px[dy,dx]):
                candidats.append((0 if any(s is o for o in supports) else 1, a))
                break
    if not candidats:
        return None, {'refus': 'aucun_clic_nouveau_sur_support_non_couvert'}
    candidats.sort(key=lambda item: (item[0], item[1]['row'], item[1]['col']))
    type_support, a = candidats[0]
    pc, sc = copy.deepcopy(courant)
    pc.step(sc, ('MOUSE', a['row'], a['col']))
    prediction = vue.rendu(sc)
    if sc.issue is not None:
        return None, {'refus': 'issue_predite_exige_examen'}
    diagnostic = {'origine': 'Explorateur.candidats', 'couverture': hyp,
        'candidats_non_repetes': len(candidats), 'modele_alternatif_admis': False,
        'contours_adjacents': len(contours),
        'support_vise': 'contour_adjacent' if type_support else 'support_initial',
        'roles_non_confirmes': True, 'risque': 'inconnu'}
    return {'statut': 'experience_role_non_couvert', 'actions': [['clic', a['col'], a['row']]],
        'question': 'Ce clic agit-il sur une forme que le modele considere statique ?',
        'predictions': [[{'nom': 'dynamique_conservee', 'image': prediction.tolist(), 'issue': None}]],
        'alternative': 'effet inconnu, aucun second modele invente',
        'but': 'inconnu', 'cout_actions': 1, 'diagnostic': diagnostic}, diagnostic
