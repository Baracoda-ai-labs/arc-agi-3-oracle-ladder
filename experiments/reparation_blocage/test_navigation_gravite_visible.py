import json
from pathlib import Path

import numpy as np
from navigation_gravite_visible import NavigationVisible

R = Path(__file__).parent


def modele(mapping=None):
    p = R / "runs/roles_autonomes_bp35_fige1/N1/partie"
    images = np.load(p.with_suffix(".npz"))["images"]
    actions = json.loads(p.with_suffix(".json").read_text())["actions"]
    if mapping is not None:
        images = mapping[images]
    return NavigationVisible(images, actions), images


def test_silhouette_retournable():
    m, ims = modele()
    assert m.pas == 6
    assert [m.position(g) for g in ims] == [(21, 39), (15, 39), (21, 39), (15, 39), (21, 39)]


def test_permutation_couleurs():
    a, ims = modele()
    b, other = modele(np.arange(16)[::-1])
    assert a.proposer(ims[-1]) == b.proposer(other[-1])


def test_progression_gravite():
    m, ims = modele()
    p = m.proposer(ims[-1])
    assert p["gravite_hypothese"] == -1
    assert p["destination"][1] < p["position"][1]
    assert p["action"] == 4
    assert p["buts_hypothetiques"] == []


def test_decalage_camera():
    m, ims = modele()
    g = np.roll(ims[-1], -1, axis=0)
    grid, pos, origin = m.lire(g)
    assert origin == (0, 5)
    assert grid.size and pos == (3, 5)
