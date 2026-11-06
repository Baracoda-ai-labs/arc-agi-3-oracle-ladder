import numpy as np
import pytest
from experience_refermeture_N3_bp35 import PREFIXES, charger_prefixe, preparer
from hypotheses_annulation import comparer
from hypotheses_refermeture import variantes


def test_refermeture_inertie_et_effet_inconnu_separes():
    _m, preds, pre = preparer()
    assert pre["issues_distinctes"] == 2 and pre["admissible_modeles"]
    for name, (im, _) in preds.items():
        assert comparer(im, preds)["compatibles"] == [name]
    assert int(np.sum(preds["reste_ouvert"][0][:-1] != preds["refermeture_locale"][0][:-1])) == 30
    other = preds["reste_ouvert"][0].copy()
    other[0, 0] = (other[0, 0] + 1) % 16
    assert comparer(other, preds)["statut"] == "hors_catalogue"


def test_ne_restaure_pas_le_reste_du_monde():
    m, _, _ = preparer()
    z, j = charger_prefixe(PREFIXES[-1])
    before, opened = z["images"][-2:]
    current = opened.copy()
    current[0, 0] = (current[0, 0] + 1) % 16
    preds = variantes(before, opened, current, j["actions"][-1], m)
    assert preds["refermeture_locale"][0][0, 0] == current[0, 0]
    modified = opened.copy()
    mask = before != opened
    mask[-1] = False
    modified[mask] = before[mask]
    with pytest.raises(ValueError, match="conservée"):
        variantes(before, opened, modified, j["actions"][-1], m)


def test_cycle_reel_appris_localement_sans_effacer_autres_observations():
    from pathlib import Path

    from support_reversible import apprendre, projeter

    m, _, _ = preparer()
    r = Path(__file__).parent / "runs/refermeture_N3_reel1"
    z = np.load(r / "N3/partie.npz")
    before, opened, closed = z["images"][-3:]
    rule = apprendre(before, opened, closed, ["clic", 33, 39], m, "contexte_local")
    assert np.array_equal(projeter(opened, rule, "contexte_local")[:-1], closed[:-1])
    assert np.array_equal(projeter(closed, rule, "contexte_local")[:-1], opened[:-1])
    assert projeter(opened, rule, "autre_niveau") is None
    unknown = opened.copy()
    x, y = rule["pixels_xy"][0]
    unknown[y, x] = (unknown[y, x] + 1) % 16
    assert projeter(unknown, rule, "contexte_local") is None
    outside = opened.copy()
    outside[0, 0] = (outside[0, 0] + 1) % 16
    assert projeter(outside, rule, "contexte_local")[0, 0] == outside[0, 0]
