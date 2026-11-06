import numpy as np
from experience_annulation_N3_bp35 import preparer
from hypotheses_annulation import comparer


def test_annulation_discriminante_apres_deplacement():
    m, preds, pre = preparer()
    assert pre["issues_distinctes"] == 4 and pre["admissible_modeles"]
    assert m.position(preds["inerte"][0]) != m.position(preds["etat_avant_derniere_action"][0])
    assert m.position(preds["etat_avant_derniere_action"][0]) != m.position(preds["etat_avant_dernier_clic"][0])
    for name, (im, _) in preds.items():
        assert comparer(im, preds)["compatibles"] == [name]


def test_nouvel_effet_pas_force_dans_catalogue_et_hud_separe():
    _, preds, _ = preparer()
    im = preds["inerte"][0].copy()
    im[-1] = (im[-1] + 1) % 16
    assert comparer(im, preds)["compatibles"] == ["inerte"]
    im[0, 0] = (im[0, 0] + 1) % 16
    assert comparer(im, preds)["statut"] == "hors_catalogue"
    assert not np.array_equal(im, preds["inerte"][0])


def test_prediction_gelee_verifiee_sur_film_prospectif():
    from pathlib import Path

    p = Path(__file__).parent / "runs/annulation_N3_reel1"
    z = np.load(p / "N3/partie.npz")
    frozen = np.load(p / "predictions.npz")
    predictions = {k: (frozen[k], None) for k in frozen.files}
    assert comparer(z["images"][-1], predictions)["compatibles"] == ["etat_avant_derniere_action"]
    assert all(comparer(frame, predictions)["compatibles"] == ["etat_avant_derniere_action"] for frame in z["film_8"])
    assert not np.array_equal(z["images"][-1][-1], z["images"][-3][-1])
