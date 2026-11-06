"""Familles et contrats orientent un examen de couches au contact, sans masquer l'écart."""
import copy
from functools import reduce
from math import gcd

import numpy as np
from chaine_coherente import Chaine
from ontologie_extensible import _familles

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import MoteurFormel
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.langue.ontologie_formelle import MECANISMES


class PerceptionGuidee(MoteurFormel):
    def __init__(self, base, points):
        self.base = copy.deepcopy(base)
        self.points = sorted(set(points))

    def signature_observation(self):
        return {'base': self.base.signature_observation(), 'calque_candidat': self.points}

    def vue(self, g):
        return self.base.vue(g)  # aucune suppression de pixel ni tolérance ajoutée

    def scene(self, g):
        sc = self.base.scene(g)
        px = np.full(sc.vue, -1, dtype=np.int16)
        for y, x, couleur in self.points:
            px[y, x] = couleur
        return Scene(sc.vue, sc.fond, sc.letterbox, [*sc.sprites,
                     {'pixels': px, 'x': 0, 'y': 0, 'couche': 2, 'tags': ['detail_cible_hypothese']}])


def questions(base, actions):
    f = _familles()
    s = f.signaux_depuis_objets([{'roles': ['controle']} for _ in base.mobiles] +
                                [{'roles': ['cible']} for _ in base.buts], actions)
    familles = f.reconnaitre(s)
    q = [{'question': 'Le déplacement attendu a-t-il lieu ?',
          'contrat': 'deplacement', 'effets': MECANISMES['deplacement']['ecrit']},
         {'question': 'Une frontière bloque-t-elle le déplacement ?',
          'contrat': 'blocage', 'effets': MECANISMES['blocage']['ecrit']}]
    if base.buts and any(n in ('navigation_sortie', 'correspondance_modele', 'selection_deplacement', 'pousse_cibles')
                         for n, _ in familles):
        q.append({'question': 'Au contact avec la cible, un détail reste-t-il au premier plan ?',
                  'type': 'rendu_partie_objet_couche', 'hypothese': True})
    return {'familles': familles, 'roles_supposes': vars(s), 'questions': q,
            'classification_revocable': True, 'scores_non_calibres': True}


def proposer_calques(base, p, images, actions):
    requis = ('mobiles', 'buts', 'statiques', 'hud', 'mouvements')
    manquants = [nom for nom in requis if not hasattr(base, nom)]
    if manquants:
        return [], {'refus': 'Contrat calques mobiles/cibles non disponible',
                    'capacites_manquantes': manquants, 'retour': 'perception'}
    dossier = questions(base, [a[0] for a in actions])
    if not any(q.get('type') == 'rendu_partie_objet_couche' for q in dossier['questions']):
        return [], {**dossier, 'refus': 'Aucune question de contact activée'}
    pc, sc = Programme(p), base.scene(images[0])
    for action in actions:
        pc.step(sc, tuple(action))
    pred, obs = base.rendu(sc), base.vue(images[-1])
    ys, xs = np.nonzero(pred != obs)
    if not len(xs):
        return [], {**dossier, 'refus': 'Aucun contre-exemple'}
    erreurs = list(zip(ys.tolist(), xs.tolist(), strict=True))
    # La classification oriente la recherche vers les cibles ; les pixels tranchent.
    cibles = {j for _, j in base.buts}
    points, periodiques = [], []
    for y, x in erreurs:
        if (y, x) in base.hud:
            return [], {**dossier, 'refus': 'Écart interface hors question de contact'}
        support = []
        for j in cibles:
            cible = base.statiques[j]
            px = cible['pixels']; xx, yy = x-cible['x'], y-cible['y']
            if 0 <= yy < px.shape[0] and 0 <= xx < px.shape[1] and px[yy, xx] == obs[y, x]:
                support.append((cible, xx, yy))
        mobiles = [s for s in sc.sprites if any(t.startswith('mobile_') for t in s['tags'])]
        couvert = any(0 <= y-s['y'] < s['pixels'].shape[0] and 0 <= x-s['x'] < s['pixels'].shape[1]
                      and s['pixels'][y-s['y'], x-s['x']] >= 0 for s in mobiles)
        if len(support) != 1 or not couvert:
            return [], {**dossier, 'refus': 'Écart non expliqué par recouvrement mobile/cible'}
        cible, xx, yy = support[0]
        points.append((y, x, int(obs[y, x])))
        dxs = [abs(d[0]) for ms in base.mouvements.values() for d in ms.values() if d[0]]
        dys = [abs(d[1]) for ms in base.mouvements.values() for d in ms.values() if d[1]]
        if not dxs or not dys:
            continue
        sx, sy = reduce(gcd, dxs), reduce(gcd, dys)
        px = cible['pixels']
        for by in range(yy % sy, px.shape[0], sy):
            for bx in range(xx % sx, px.shape[1], sx):
                if px[by, bx] >= 0:
                    periodiques.append((cible['y']+by, cible['x']+bx, int(px[by, bx])))
    lots = [{'actions': [{'action': a[0]}]} for a in actions]
    valides, essais = [], []
    for nom, pts in [('detail_local', points), ('detail_periodique', periodiques)]:
        if not pts:
            continue
        v = PerceptionGuidee(base, pts)
        c = Chaine(v, p, images, lots, sorted({tuple(a) for a in actions}),
                   coups_deja_joues=len(actions), reserve=80)
        controle, courant = c.rejouer()
        essais.append({'hypothese': nom, 'points': v.points, 'controle': controle})
        if courant is not None:
            valides.append((nom, c))
    dossier.update(pixels_ecart=erreurs, hypothese='détail de cible visible au-dessus du mobile',
                   essais=essais, causalite_prouvee=False)
    return valides, dossier
