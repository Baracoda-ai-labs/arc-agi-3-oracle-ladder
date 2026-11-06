"""Induction bornée de contact → retour collectif, à partir d'images observées."""
import copy
import hashlib
from itertools import product

import numpy as np
from chaine_coherente import Chaine
from contact_observe import PerceptionContact, programme, rectangles

from chrysalide.arc3.moteur import NOMS
from chrysalide.langue import depuis_python, vers_python


class PerceptionRetour(PerceptionContact):
    def __init__(self, h, danger):
        super().__init__(h, True)
        self.danger = danger
        self.identites = {}
        self.origines = None

    def signature_observation(self):
        return {**super().signature_observation(), 'danger': self.danger, 'methode': 'contact_retour_identites_temporelles', 'origines': self.origines}

    @staticmethod
    def cle(g):
        return hashlib.sha256(np.asarray(g, dtype=np.int16).tobytes()).hexdigest()

    def suivre(self, images, actions):
        """Identités par déplacements autorisés, égalité exacte du masque, refus d'ambiguïté."""
        if len(images) != len(actions)+1:
            raise ValueError('Suivi non aligné')
        origine = tuple(rectangles(images[0], self.hypothese['couleur']))
        precedent = origine
        connus = {self.cle(images[0]): origine}
        for image, action in zip(images[1:], actions, strict=True):
            options = []
            for i, (x, y, w, hh) in enumerate(precedent):
                dx, dy = self.hypothese['mouvements'][(action, i)]
                options.append({(x, y, w, hh), (x+int(dx*w), y+int(dy*hh), w, hh)})
            candidats = set(product(*options)) | {origine}
            valides = []
            for paire in candidats:
                masque = np.zeros(np.asarray(image).shape, bool)
                surface = 0
                for x, y, w, hh in paire:
                    if not (0 <= x <= 64-w and 0 <= y <= 64-hh):
                        break
                    masque[y:y+hh, x:x+w] = True
                    surface += w*hh
                else:
                    if masque.sum() == surface and np.array_equal(masque, np.asarray(image) == self.hypothese['couleur']):
                        valides.append(paire)
            if len(valides) != 1:
                raise ValueError(f'Identités ambiguës ou mouvement inconnu : {len(valides)}')
            precedent = valides[0]
            cle = self.cle(image)
            if cle in connus and connus[cle] != precedent:
                raise ValueError('Image identique avec identités incompatibles')
            connus[cle] = precedent
        self.identites, self.origines = connus, origine

    def vue(self, g):
        a = np.asarray(g)
        h = self.hypothese
        b = (~np.isin(a, list(h['libres'] | {h['couleur']}))).astype(np.int16)
        b[a == self.danger] = 4
        for y, x in h['hud']:
            b[y, x] = 0
        rects = self.identites.get(self.cle(g))
        if rects is None:
            raise ValueError('Observation à apparier avant projection')
        for i, (x, y, w, hh) in enumerate(rects):
            b[y:y+hh, x:x+w] = i+2
        return b


def regle_retour(h, initiale, collectif=True):
    p = copy.deepcopy(programme(h, initiale))
    p['regles'][-1]['phase'] = 2
    contact = ['ou', *[['existe', '$o', ['objets', {'couleur': i+2}],
                        ['non', ['libre', '$o', 0, 0, {'couleur': 4}]]] for i in range(2)]]
    effets = []
    for i, (x, y, _, _) in enumerate(rectangles(initiale, h['couleur'])):
        effet = ['placer', '$o', x, y]
        if not collectif:
            effet = ['si_alors', ['non', ['libre', '$o', 0, 0, {'couleur': 4}]], [effet], []]
        effets.append(['pour', '$o', ['objets', {'couleur': i+2}], [effet]])
    p['regles'].insert(-1, {'nom': 'contact_retour_observe', 'phase': 1,
                           'quand': contact, 'alors': effets})
    assert depuis_python(vers_python(p)) == p
    return p


def apprendre(h, images, actions, film):
    """Dernière transition = contre-exemple ; aucun état interne du jeu consulté."""
    if len(images) != len(actions)+1 or len(film) < 2:
        raise ValueError('Film temporel et transitions alignées requis')
    origine = rectangles(images[0], h['couleur'])
    avant = rectangles(images[-2], h['couleur'])
    apres = rectangles(images[-1], h['couleur'])
    if apres != origine or avant == origine:
        raise ValueError('Retour aux positions initiales non observé')
    couleurs = set()
    contacts = []
    for i, (x, y, w, hh) in enumerate(avant):
        dx, dy = h['mouvements'][(actions[-1], i)]
        xx, yy = x+int(dx*w), y+int(dy*hh)
        if not (0 <= xx <= 64-w and 0 <= yy <= 64-hh):
            raise ValueError('Destination hors image')
        couleurs.update(np.asarray(images[-2])[yy:yy+hh, xx:xx+w].ravel().tolist())
        # Trace d'entrée ou de changement visuel à la destination dans le film.
        contacts.append(any(np.any(np.asarray(f)[yy:yy+hh, xx:xx+w] !=
                                   np.asarray(images[-2])[yy:yy+hh, xx:xx+w]) for f in film[:-1]))
    if not any(contacts):
        raise ValueError('Aucune interaction temporelle observée')
    couleurs -= h['libres'] | {h['couleur']}
    lots = [{'actions': [{'action': NOMS[a]}]} for a in actions]
    essais, valides = [], []
    for couleur in sorted(couleurs):
        for collectif in (False, True):
            perception = PerceptionRetour(h, couleur)
            perception.suivre(images, actions)
            p = regle_retour(h, images[0], collectif)
            c = Chaine(perception, p, [g.tolist() for g in images], lots,
                       [(NOMS[k],) for k in range(1, 5)])
            controle, etat = c.rejouer()
            essais.append({'couleur_candidate': couleur, 'collectif': collectif,
                           'controle': controle, 'compatible': etat is not None})
            if etat is not None:
                valides.append((perception, p))
    if len(valides) != 1:
        raise ValueError(f'Hypothèse ambiguë ou absente : {len(valides)} ; {essais}')
    perception, p = valides[0]
    return perception, p, {'statut': 'compatible_sur_prefixe_developpement',
        'observation': 'Les deux mobiles reviennent aux positions initiales après interaction dans le film.',
        'hypothese': 'Un contact avec cette classe visuelle déclenche un retour collectif.',
        'concepts': ['mobile', 'zone_candidate', 'contact', 'position_initiale', 'retour_collectif'],
        'essais': essais, 'limite': 'Une occurrence ; causalité et généralisation non démontrées.'}
