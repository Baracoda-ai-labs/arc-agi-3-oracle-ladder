import numpy as np
from signe_visuel import detecter


def frames(masses):
    out = []
    for n in masses:
        g = np.zeros((8, 8), dtype=int)
        g[2, :n] = 7
        out.append(g)
    return out


def test_amputation_puis_disparition_sans_statut():
    assert detecter(frames([6, 6, 2, 0]), {"couleurs_exclusives": [7], "masse_min": 6})["debut"] == 2


def test_mouvement_et_hud_ne_sont_pas_rupture():
    fs = frames([6] * 4)
    fs = [np.roll(g, i, axis=1) for i, g in enumerate(fs)]
    fs[0][-1] = 7
    assert detecter(fs, {"couleurs_exclusives": [7], "masse_min": 6})["debut"] is None


def test_flash_isole_et_debut_censure():
    p = {"couleurs_exclusives": [7], "masse_min": 6}
    assert detecter(frames([6, 2, 6]), p)["debut"] is None
    assert detecter(frames([2, 0, 0]), p)["debut"] is None
    assert detecter(frames([6, 0]), p)["debut"] is None


def test_couleur_non_exclusive_ne_prouve_rien():
    assert detecter(frames([6, 0, 0]), {"couleurs_exclusives": [], "masse_min": None})["statut"] == "non_observable"


def test_exclusivite_reverifiee_avant_action(monkeypatch):
    from types import SimpleNamespace

    import signe_visuel

    ref = np.zeros((8, 8), dtype=int)
    ref[1, 1:3] = [7, 8]
    context = ref.copy()
    context[4, 4] = 8
    actor = {"tags": ["controle"], "x": 1, "y": 1, "pixels": np.array([[7, 8]])}
    monkeypatch.setattr(signe_visuel, "scene_image", lambda g, m: SimpleNamespace(sprites=[actor]))
    m = SimpleNamespace(palette={7, 8}, images=[ref])
    assert signe_visuel.apprendre(m)["couleurs_exclusives"] == [7, 8]
    assert signe_visuel.apprendre(m, [context]) == {"couleurs_exclusives": [7], "masse_min": 1}
