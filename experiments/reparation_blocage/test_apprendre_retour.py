import numpy as np
import pytest
from apprendre_retour import apprendre


@pytest.mark.parametrize('mobile,sol,danger,x,y', [(12, 4, 7, 8, 8), (3, 9, 15, 18, 24)])
def test_induction_retour_collectif_et_refus_local(mobile, sol, danger, x, y):
    h = {'couleur': mobile, 'libres': {sol}, 'solides': set(), 'hud': set(),
         'mouvements': {(2, 0): (0, 1), (2, 1): (0, 1)}}
    def image(d):
        a = np.full((64, 64), sol)
        a[y+8:y+12, x+16:x+20] = danger
        for xx in (x, x+16):
            a[y+d:y+d+4, xx:xx+4] = mobile
        return a
    images = np.array([image(0), image(4), image(0)])
    film = np.array([image(8), image(0)])
    perception, p, rapport = apprendre(h, images, [2, 2], film)
    assert perception.danger == danger
    assert [r['compatible'] for r in rapport['essais']] == [False, True]
    assert p['regles'][-2]['nom'] == 'contact_retour_observe'
    assert rapport['essais'][-1]['controle']['compilation_fidele']
    with pytest.raises(ValueError, match='Film temporel'):
        apprendre(h, images, [2, 2], film[-1:])
    with pytest.raises(ValueError, match='Retour'):
        apprendre(h, np.array([image(0), image(4), image(8)]), [2, 2], film)


def test_identites_conservees_apres_contact_visuel_et_croisement():
    from apprendre_retour import PerceptionRetour
    h = {'couleur': 12, 'libres': {4}, 'solides': set(), 'hud': set(),
         'mouvements': {(4, 0): (1, 0), (4, 1): (-1, 0)}}
    def image(x1, x2):
        a = np.full((64, 64), 4)
        a[20:24, x1:x1+4] = 12
        a[24:28, x2:x2+4] = 12
        return a
    images = [image(10, 18), image(14, 14), image(18, 10)]
    p = PerceptionRetour(h, 7)
    p.suivre(images, [4, 4])
    assert p.vue(images[1])[20, 14] == 2
    assert p.vue(images[1])[24, 14] == 3
    assert p.vue(images[2])[20, 18] == 2
    assert p.vue(images[2])[24, 10] == 3
    with pytest.raises(ValueError, match='apparier'):
        p.vue(image(30, 40))
