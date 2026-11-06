"""Objets temporels existants → mouvements et buts candidats, sans victoire préalable."""
from collections import Counter
from itertools import pairwise

import numpy as np

from chrysalide.arc3.masque import Masque
from chrysalide.arc3.moteur import NOMS, MoteurFormel, _composantes, _sprite
from chrysalide.arc3.objets_temps import Pisteur
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.langue import depuis_python, vers_python


def localiser(g, motif):
    h, w = motif.shape
    fen = np.lib.stride_tricks.sliding_window_view(np.asarray(g), (h, w))
    masque = motif >= 0
    ys, xs = np.nonzero((fen[..., masque] == motif[masque]).all(axis=-1))
    if len(xs) != 1:
        raise ValueError(f'Appariement non unique : {len(xs)}')
    return int(xs[0]), int(ys[0])


class ObjetsVariables(MoteurFormel):
    def __init__(self, images, actions, contact=False, identites_temporelles=False, masque_court=False, jauge_validee=False, clics_negatifs=False, films=None):
        if len(images) != len(actions)+1 or not actions:
            raise ValueError('Transitions nécessaires, pas de victoire requise')
        images = [np.asarray(g) for g in images]
        self.clics_negatifs = clics_negatifs
        self.preuves_clics_negatifs = []
        if clics_negatifs:
            from clics_negatifs import normaliser
            actions, self.preuves_clics_negatifs = normaliser(images, actions, films)
        self.contact = contact
        self.identites_temporelles = identites_temporelles
        self.masque_court = masque_court
        self.jauge_validee = jauge_validee
        self.preuves_jauge = []
        self._positions_connues = {}
        masque, pisteur = Masque(court=masque_court), Pisteur(revisable=True, contact=contact)
        for a, b in pairwise(images):
            masque.observer(a.tolist(), b.tolist())
        self.hud = masque.cellules()
        if jauge_validee:
            from jauges_observees import jauges_validees
            regions, self.preuves_jauge = jauges_validees(images, actions)
            self.hud = self.hud | regions
        self.fond = Counter(images[0].ravel().tolist()).most_common(1)[0][0]
        propres = []
        for image in images:
            g = image.copy()
            for y, x in self.hud:
                g[y, x] = self.fond
            propres.append(g)
            objets = pisteur.observer(g)
        self.mobiles, self.mouvements = [], {}
        positions_mobiles = []
        suivis = {}
        for cases in objets.values():
            if not cases or len(cases) > 400:
                continue
            ys, xs = zip(*cases)
            y, x = min(ys), min(xs)
            motif = np.full((max(ys)-y+1, max(xs)-x+1), -1, dtype=np.int16)
            for yy, xx in cases:
                motif[yy-y, xx-x] = propres[-1][yy, xx]
            try:
                positions = [localiser(g, motif) for g in propres]
            except ValueError:
                if not identites_temporelles:
                    continue
                from objets_identites import occurrences, suivre_motif
                signature = (motif.shape, motif.tobytes())
                if signature not in suivis:
                    try:
                        suivis[signature] = suivre_motif(propres, motif, len(occurrences(propres[0], motif)))
                    except ValueError:
                        suivis[signature] = None
                suivi = suivis[signature]
                if suivi is None or (x,y) not in suivi[-1]:
                    continue
                indice = suivi[-1].index((x,y))
                positions = [ps[indice] for ps in suivi]
            if len(set(positions)) == 1:
                continue
            mouvements = {}
            for action in sorted(set(actions)):
                ds = {(b[0]-a[0], b[1]-a[1]) for k, (a, b) in enumerate(pairwise(positions))
                      if actions[k] == action} - {(0, 0)}
                if len(ds) > 1:
                    raise ValueError('Déplacement contextuel non encore expliqué')
                mouvements[action] = next(iter(ds)) if ds else (0, 0)
            i = len(self.mobiles)
            self.mobiles.append(motif)
            positions_mobiles.append(positions)
            self.mouvements[i] = mouvements
        if not self.mobiles:
            raise ValueError('Aucun objet mobile apparié')
        self.initiales = [positions[0] for positions in positions_mobiles]
        if identites_temporelles:
            self._positions_connues = {np.asarray(g,dtype=np.int16).tobytes(): [ps[k] for ps in positions_mobiles] for k,g in enumerate(propres)}
        # Arrière-plan candidat : hypothèse de sol homogène sous les mobiles.
        decor = propres[0].copy()
        for m, (x, y) in zip(self.mobiles, self.initiales):
            v = decor[y:y+m.shape[0], x:x+m.shape[1]]
            v[m >= 0] = self.fond
        self.decor = decor
        self.statiques = [_sprite(o) for o in _composantes(decor, self.fond)]
        self.buts = []
        for i, motif in enumerate(self.mobiles):
            for j, s in enumerate(self.statiques):
                px = np.asarray(s['pixels'])
                if px.shape == motif.shape and np.array_equal(px >= 0, motif >= 0):
                    self.buts.append((i, j))

    def signature_observation(self):
        return {'methode': 'pisteur_motifs_variables', **({'clics_negatifs': self.preuves_clics_negatifs} if self.clics_negatifs else {}), 'contact_candidat': self.contact, 'motifs': [m.tolist() for m in self.mobiles],
                'identites_temporelles': self.identites_temporelles, 'masque_court': self.masque_court, 'jauge_validee': self.jauge_validee, 'fond': int(self.fond), 'hud': sorted(map(list, self.hud)), 'decor': self.decor.tolist()}

    def vue(self, g):
        a = np.asarray(g).copy()
        for y, x in self.hud:
            a[y, x] = self.fond
        return a

    def positions_observees(self, g):
        a = self.vue(g)
        if self.identites_temporelles and np.asarray(a,dtype=np.int16).tobytes() in self._positions_connues:
            return self._positions_connues[np.asarray(a,dtype=np.int16).tobytes()]
        return [localiser(a, m) for m in self.mobiles]

    def scene(self, g):
        # Reconstituer depuis les observations, sans injecter l'état du jeu.
        a = self.vue(g)
        sprites = []
        for j, s in enumerate(self.statiques):
            sprites.append({**s, 'pixels': s['pixels'].copy(), 'tags': [f'statique_{j}']})
        for i, (m, (x,y)) in enumerate(zip(self.mobiles, self.positions_observees(g))):
            sprites.append({'pixels': m.copy(), 'x': x, 'y': y, 'couche': 1, 'tags': [f'mobile_{i}']})
        return Scene(a.shape, self.fond, self.fond, sprites)

    def programme(self, cible=None):
        i_cible, j_cible = cible if cible is not None else (None, None)
        regles = []
        for i, mouvements in self.mouvements.items():
            h, w = self.mobiles[i].shape
            for action, (dx, dy) in mouvements.items():
                libre = ['et', ['>=', ['+', ['x', '$o'], dx], 0],
                         ['<=', ['+', ['x', '$o'], dx+w], 64],
                         ['>=', ['+', ['y', '$o'], dy], 0], ['<=', ['+', ['y', '$o'], dy+h], 64],
                         *[['libre', '$o', dx, dy, {'tag': f'statique_{j}'}]
                           for j in range(len(self.statiques)) if j != j_cible]]
                regles.append({'nom': f'mouvement_{i}_{action}', 'phase': 0,
                    'quand': ['=', ['action'], 'MOUSE' if action == 6 else NOMS[action]],
                    'alors': [['pour', '$o', ['objets', {'tag': f'mobile_{i}'}],
                              [['si_alors', libre, [['deplacer', '$o', dx, dy]], []]]]]})
        if cible is not None:
            cible_obj = self.statiques[j_cible]
            regles.append({'nom': 'but_correspondance_hypothese', 'phase': 1,
                'quand': ['existe', '$o', ['objets', {'tag': f'mobile_{i_cible}'}],
                          ['et', ['=', ['x', '$o'], cible_obj['x']], ['=', ['y', '$o'], cible_obj['y']]]],
                'alors': [['niveau_suivant']]})
        p = {'mode': 'lois', 'etat': {}, 'regles': regles}
        assert depuis_python(vers_python(p)) == p
        return p
