"""Hypothèse géométrique restreinte, apprise des images et d'une fin de niveau observée."""
from collections import Counter
from itertools import pairwise

import numpy as np

from chrysalide.arc3.masque import Masque
from chrysalide.arc3.moteur import NOMS, MoteurFormel, _composantes, _sprite
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.langue import depuis_python, vers_python


def rectangles(image, couleur):
    objets = sorted((o for o in _composantes(np.asarray(image), -999) if o[0] == couleur),
                    key=lambda o: (o[2], o[3]))
    resultat = []
    for _, forme, x, y in objets:
        w, h = max(dx for dx, _ in forme) + 1, max(dy for _, dy in forme) + 1
        if len(forme) != w * h or not 2 <= w <= 16 or not 2 <= h <= 16:
            raise ValueError('Composantes non rectangulaires ou hors domaine')
        resultat.append((int(x), int(y), int(w), int(h)))
    if len(resultat) != 2:
        raise ValueError('Deux mobiles distincts requis')
    return resultat


def chevauche(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    return x < xx + ww and xx < x + w and y < yy + hh and yy < y + h


def induire(images, actions, victoire):
    """La dernière image est le nouveau niveau, exclue de l'induction géométrique."""
    if not victoire or len(images) != len(actions) + 1:
        raise ValueError('Trajectoire gagnante complete requise')
    candidats = []
    for couleur in sorted(set(np.asarray(images[0]).ravel().tolist())):
        try:
            etats = [rectangles(g, couleur) for g in images[:-1]]
        except ValueError:
            continue
        mesures = {}
        libres = set()
        for t, action in enumerate(actions[:-1]):
            if action not in NOMS or action not in (1, 2, 3, 4):
                continue
            for i, (avant, apres) in enumerate(zip(etats[t], etats[t + 1], strict=True)):
                x, y, w, h = avant
                xx, yy, ww, hh = apres
                if (w, h) != (ww, hh):
                    break
                if (xx, yy) != (x, y):
                    mesures.setdefault((action, i), Counter())[((xx - x) / w, (yy - y) / h)] += 1
                    masque = np.zeros((64, 64), bool)
                    masque[y:y+h, x:x+w] = True
                    masque[yy:yy+h, xx:xx+w] = False
                    libres.update(np.asarray(images[t + 1])[masque].tolist())
        if len(mesures) != 8 or any(len(v) != 1 for v in mesures.values()):
            continue
        mouvements = {k: next(iter(v)) for k, v in mesures.items()}
        prochain = []
        for i, (x, y, w, h) in enumerate(etats[-1]):
            dx, dy = mouvements[(actions[-1], i)]
            prochain.append((x + dx * w, y + dy * h, w, h))
        if not chevauche(*prochain):
            continue
        masque = Masque()
        for a, b in pairwise(images[:-1]):
            masque.observer(np.asarray(a).tolist(), np.asarray(b).tolist())
        solides = set()
        for t, action in enumerate(actions[:-1]):
            if action not in (1, 2, 3, 4):
                continue
            for i, (avant, apres) in enumerate(zip(etats[t], etats[t + 1], strict=True)):
                if avant != apres:
                    continue
                x, y, w, h = avant
                dx, dy = mouvements[(action, i)]
                xx, yy = x + int(dx * w), y + int(dy * h)
                if 0 <= xx <= 64 - w and 0 <= yy <= 64 - h:
                    solides.update(np.asarray(images[t])[yy:yy+h, xx:xx+w].ravel().tolist())
        candidats.append({'couleur': couleur, 'mouvements': mouvements, 'libres': libres - {couleur},
                          'solides': solides - libres - {couleur}, 'hud': masque.cellules(),
                          'but': 'contact_mobiles_suppose_depuis_victoire'})
    if len(candidats) != 1:
        raise ValueError(f'Induction ambigue : {len(candidats)} candidats')
    return candidats[0]


class PerceptionContact(MoteurFormel):
    def __init__(self, hypothese, prudente=False):
        self.hypothese, self.prudente = hypothese, prudente

    def signature_observation(self):
        h = self.hypothese
        return {'methode': 'contact_geometrique', 'prudente': self.prudente,
                'couleur': h['couleur'], 'libres': sorted(h['libres']),
                'solides': sorted(h['solides']), 'hud': sorted(map(list, h['hud']))}

    def vue(self, g):
        a = np.asarray(g)
        h = self.hypothese
        if self.prudente:
            bloque = ~np.isin(a, list(h['libres'] | {h['couleur']}))
        else:
            bloque = np.isin(a, list(h['solides']))
        b = bloque.astype(np.int16)
        for y, x in h['hud']:
            b[y, x] = 0
        for i, (x, y, w, hh) in enumerate(rectangles(a, h['couleur'])):
            b[y:y+hh, x:x+w] = i + 2
        return b

    def scene(self, g):
        b = self.vue(g)
        return Scene(b.shape, 0, 0, [_sprite(o) for o in _composantes(b, 0)])


def programme(hypothese, image):
    rects = rectangles(image, hypothese['couleur'])
    regles = []
    for (action, i), (vx, vy) in sorted(hypothese['mouvements'].items()):
        w, h = rects[i][2:]
        if vx * w != int(vx * w) or vy * h != int(vy * h):
            raise ValueError('Echelle non entiere')
        dx, dy = int(vx * w), int(vy * h)
        libre = ['et', ['libre', '$o', dx, dy, {'couleur': 1}],
                 ['>=', ['+', ['x', '$o'], dx], 0], ['<=', ['+', ['+', ['x', '$o'], dx], w], 64],
                 ['>=', ['+', ['y', '$o'], dy], 0], ['<=', ['+', ['+', ['y', '$o'], dy], h], 64]]
        regles.append({'nom': f'mouvement_{i}_{action}', 'phase': 0,
            'quand': ['=', ['action'], NOMS[action]],
            'alors': [['pour', '$o', ['objets', {'couleur': i + 2}],
                      [['si_alors', libre, [['deplacer', '$o', dx, dy]], []]]]]})
    regles.append({'nom': 'but_contact_suppose', 'phase': 1,
        'quand': ['existe', '$a', ['objets', {'couleur': 2}],
                  ['existe', '$b', ['objets', {'couleur': 3}], ['chevauche', '$a', '$b']]],
        'alors': [['niveau_suivant']]})
    p = {'mode': 'lois', 'etat': {}, 'regles': regles}
    assert depuis_python(vers_python(p)) == p
    return p
