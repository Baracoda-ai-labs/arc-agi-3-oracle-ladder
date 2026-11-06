"""Contrôles métamorphiques sur trace réelle : ce n'est pas une généralisation ARC."""

import json
from pathlib import Path

import numpy as np
import pytest
from chaine_coherente import Chaine
from selection_observee import SelectionObservee

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import NOMS

R = Path(__file__).parent / "ka59_roles"


def donnees(n=32):
    z = np.load(R / "session/N1/partie.npz")
    actions = [r["action"] for r in json.loads((R / "session/N1/partie.json").read_text())["rows"]][:n]
    return z["images"][: n + 1], actions, [z[f"film_{k}"] for k in range(1, n + 1)]


def chaine(gs, actions, films, contact="sortie"):
    v = SelectionObservee(gs, actions, contact=contact, films=films)
    lots = [
        {"actions": [{"action": NOMS[a]} if isinstance(a, int) else {"action": "MOUSE", "row": a[2], "col": a[1]}]}
        for a in actions
    ]
    return v, Chaine(v, v.programme(), gs.tolist(), lots, [(NOMS[k],) for k in range(1, 5)], films=films)


@pytest.mark.parametrize("permutation,dx,dy", [(False, 0, 0), (True, 0, 0), (True, 3, -6)])
def test_rejeu_renommage_et_translation(permutation, dx, dy):
    gs, actions, films = donnees()

    def transformer(g):
        r = np.full_like(g, int(g[0, 0]))
        # Translation du plateau seul ; le HUD demeure au bord de l'écran.
        for y in range(63):
            if not 0 <= y + dy < 63:
                continue
            for x in range(64):
                if 0 <= x + dx < 64:
                    r[y + dy, x + dx] = g[y, x]
        r[63] = g[63]
        return (r * 5 + 3) % 16 if permutation else r

    images = np.array([transformer(g) for g in gs])
    films = [np.array([transformer(g) for g in f]) for f in films]
    actions = [a if isinstance(a, int) else ["clic", a[1] + dx, a[2] + dy] for a in actions]
    v, c = chaine(images, actions, films)
    ctrl, _ = c.rejouer()
    assert ctrl["rejeu"] and ctrl["compilation_fidele"], ctrl
    assert ctrl["transitions"] == 32
    assert v.sorties and v.preuves_sortie[-1]["coup"] == 32
    # La glissade sans condition d'arrêt doit rester réfutée.
    _, err = chaine(images, actions, films, contact="glisse")
    assert err.rejouer()[0]["premiere_divergence"] == 32


def test_suffixe_gagnant_prevu_avant_execution():
    gs, actions, films = donnees()
    v, c = chaine(gs, actions, films)
    exp = json.loads((R / "apres_film_surface/experience.json").read_text())
    tuples = [(NOMS[a],) if isinstance(a, int) else ("MOUSE", a[2], a[1]) for a in exp["actions"]]
    ok, preuve = c.verifier_plan(tuples)
    assert ok and preuve["pas"] == 7
    z = np.load(R / "session/N1/partie.npz")
    p = Programme(v.programme())
    sc = v.scene(gs[0])
    for a in actions:
        p.step(sc, (NOMS[a],) if isinstance(a, int) else ("MOUSE", a[2], a[1]))
    for k, a in enumerate(tuples):
        p.step(sc, a)
        if k < 6:
            assert np.array_equal(v.rendu(sc), v.vue(z["images"][33 + k]))
    bilan = json.loads((R / "session/bilan.json").read_text())
    assert bilan["coups_reels"] == 39 and bilan["niveaux_gagnes"] == 1
    assert not bilan["jeu_gagne"]


def test_replanification_depuis_etat_observe():
    from plan_selection_dynamique import chercher

    gs, actions, films = donnees()
    v, c = chaine(gs, actions, films)
    plan, infos = chercher(c, v, secondes=3)
    assert plan is not None, infos
    assert c.verifier_plan(plan)[0]
    assert any(a[0] == "MOUSE" for a in plan)


def test_frame_terminale_avant_changement_niveau():
    z = np.load(R / "session/N1/partie.npz")
    exp = json.loads((R / "apres_film_surface/experience.json").read_text())
    pred = np.array(exp["predictions"][-1][0]["image"])
    obs = z["film_39"][0].copy()
    for y, x in exp["hud"]:
        pred[y, x] = obs[y, x] = 0
    assert np.array_equal(pred, obs)
    assert len(z["film_39"]) == 2  # La seconde image est le niveau suivant.
