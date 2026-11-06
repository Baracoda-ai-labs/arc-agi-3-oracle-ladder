"""Contacts nouveaux à des coordonnées et couleurs libres ; contrôles avant SDK."""
import numpy as np
from chaine_coherente import Chaine
from contact_observe import PerceptionContact, programme


def exemple_contact():
    h = {'couleur': 12, 'libres': {4}, 'solides': {9}, 'hud': set(),
         'mouvements': {(4, 0): (1, 0), (4, 1): (-1, 0)}}
    def image(x, xx):
        g = np.full((64, 64), 4, dtype=int)
        g[8:20, 22:26] = 7
        g[10:14, x:x+4] = 12
        g[10:14, xx:xx+4] = 12
        return g.tolist()
    return h, image


def test_contact_repare_le_prefixe_sans_memoriser_la_position():
    h, image = exemple_contact()
    grilles = [image(10, 30), image(14, 26), image(18, 26)]
    lots = [{'actions': [{'action': 'RIGHT'}]}] * 2
    p = programme(h, grilles[0])
    ancien = Chaine(PerceptionContact(h), p, grilles, lots, [('RIGHT',)])
    nouveau = Chaine(PerceptionContact(h, True), p, grilles, lots, [('RIGHT',)])
    assert ancien.rejouer()[1] is None
    controle, etat = nouveau.rejouer()
    assert etat is not None and controle['compilation_fidele']
    assert ancien.signature()['perception'] != nouveau.signature()['perception']


def test_couleur_libre_preservee_dans_la_projection_prudente():
    h, image = exemple_contact()
    v = PerceptionContact(h, True).vue(image(10, 30))
    assert v[10, 10] == 2 and v[10, 30] == 3
    assert v[10, 22] == 1 and v[10, 18] == 0
