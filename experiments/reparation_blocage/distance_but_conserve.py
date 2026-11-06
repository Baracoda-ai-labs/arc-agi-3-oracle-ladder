"""Score de la théorie existante appliqué aux objets du simulateur conservé."""
import copy

import numpy as np

from chrysalide.arc3.logique.plan import distance_but
from chrysalide.arc3.logique.export_langage import exporter


def pour_chaine(chaine):
    th = copy.deepcopy(chaine.perception.th_releve)
    programme, non = exporter(th, chaine.perception.tr.taille)
    if non or programme != chaine.programme or not th.but or th.but[0] != 'marques':
        raise ValueError('Score de marques exige une théorie synchronisée')
    formes = {}

    def estimer(scene, etat):
        monde = []
        for sprite in scene.sprites:
            if not sprite['visible']:
                continue
            pixels = sprite['pixels']
            cache = formes.get(id(pixels))
            if cache is None or cache[0] is not pixels:
                p = np.asarray(pixels)
                composantes = []
                for couleur in np.unique(p):
                    if couleur < 0:
                        continue
                    ys, xs = np.nonzero(p == couleur)
                    composantes.append((int(couleur), frozenset(zip(map(int, xs), map(int, ys)))))
                cache = formes[id(pixels)] = (pixels, composantes)
            monde.extend((couleur, forme, sprite['x'], sprite['y']) for couleur, forme in cache[1])
        return distance_but(th, tuple(monde))

    return estimer
