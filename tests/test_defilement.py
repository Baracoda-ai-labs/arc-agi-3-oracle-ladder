"""D (CHRYS_DEFILEMENT / CHRYS_LISSAGE, bp35) : écran qui suit le joueur → monde fixe en mémoire ; HUD hors du monde."""
import numpy as np

from chrysalide.arc3.logique.faits import defilement, lisser


def _monde():
    rng = np.random.default_rng(0)
    return rng.integers(1, 5, size=(40, 10))


def test_camera_retrouvee_et_monde_fixe():
    m = _monde()
    ecrans = [m[y:y + 20].copy() for y in (10, 10, 4, 16)]  # la caméra monte de 6, puis descend de 12
    for e in ecrans:
        e[-1, :] = 9  # HUD : dernière rangée d'écran, immobile
    ecrans[1][-1, :3] = 7  # le HUD change (minuterie)
    mondes, cam = defilement(ecrans, fond=0)
    assert [c[1] for c in cam] == [6, 6, 0, 12]
    assert all((mondes[-1][y + 6] == m[y + 10]).all() for y in range(12))  # le monde vu est recollé sans le HUD
    assert not (mondes[-1] == 9).any() and not (mondes[-1] == 7).any()


def test_objet_qui_bouge_nest_pas_un_defilement():
    e0 = np.zeros((20, 20), int)
    e1 = e0.copy()
    e0[5:8, 5:8] = 3
    e1[5:8, 9:12] = 3  # 9 cases sur 400 changent : un objet bouge, la caméra reste
    assert defilement([e0, e1], fond=0)[1] is None


def test_lisser_efface_les_points_isoles():
    g = np.zeros((8, 8), int)
    g[3, 3] = 5
    g[0:2, 6:8] = 4  # bloc de 4 : gardé
    assert lisser(g)[3, 3] == 0 and (lisser(g)[0:2, 6:8] == 4).all()
