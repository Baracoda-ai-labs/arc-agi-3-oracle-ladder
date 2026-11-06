from types import SimpleNamespace

import numpy as np
from perception_hierarchique import contact_observe, decomposer


def test_parties_exactes_et_motif_independant_fond(monkeypatch):
    import perception_hierarchique as p

    from chrysalide.arc3.ontologie_exec import Scene

    g = np.full((64, 64), 5)
    g[:, 32:] = 10
    motif = np.array([[15, 15, 15], [11, 0, 11]])
    g[1:3, 1:4] = motif
    g[1:3, 37:40] = motif

    def base(image, modele):
        return Scene(
            (64, 64),
            5,
            0,
            [
                {
                    "x": 0,
                    "y": 0,
                    "pixels": np.where(image == c, c, -1),
                    "tags": [f"couleur_{c}"],
                    "couleur": c,
                    "couche": 0,
                    "nom": str(c),
                }
                for c in (5, 10)
            ],
        )

    monkeypatch.setattr(p, "scene_image", base)
    m = SimpleNamespace(sol=10, pas=6, lire=lambda image: (None, None, (0, 0)))
    sc, parents = decomposer(g, m)
    assert len(parents) == 2 and parents[0]["tags"] == parents[1]["tags"]
    assert np.array_equal(sc.image()[:-1], g[:-1])
    assert len([o for o in sc.sprites if "parent" in o.get("attrs", {})]) == 6
    shifted, _ = decomposer(g, m, origine=(12, 18))
    assert np.array_equal(shifted.image()[:-1], g[:-1])


def test_contact_pixels_ne_confond_pas_boites_vides():
    a = {"x": 0, "y": 0, "pixels": np.array([[1, -1, -1]])}
    b = {"x": 1, "y": 0, "pixels": np.array([[-1, 2]])}
    r = contact_observe(a, b)
    assert r["distance_pixels"] == 2 and r["collision_cachee"] == "inconnue"
