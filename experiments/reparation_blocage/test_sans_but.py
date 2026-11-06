import json
from pathlib import Path

import numpy as np
from boucle_roles_autonome import comparer
from chaine_coherente import Chaine
from experience_sans_but import proposer
from objets_variables import ObjetsVariables
from roles_observes import PerceptionRoles

from chrysalide.arc3.moteur import NOMS


def scene(x, y):
    g = np.full((64, 64), 9, dtype=np.int16)
    g[8:48, 8:48] = 1
    g[y : y + 3, x : x + 3] = 7
    return g


def test_perception_et_dynamique_sans_aucun_but():
    gs = [scene(20, 20), scene(23, 20), scene(20, 20), scene(20, 23), scene(20, 20)]
    actions = [4, 3, 2, 1]
    assert ObjetsVariables(gs, actions).buts == []
    v = PerceptionRoles(gs, actions)
    assert v.buts == []
    p = v.programme()
    assert all(r["nom"] != "but_correspondance_hypothese" for r in p["regles"])
    c = Chaine(v, p, [g.tolist() for g in gs], [{"actions": [{"action": NOMS[a]}]} for a in actions], [])
    assert c.rejouer()[0]["rejeu"]
    e, d = proposer(gs, actions, [np.array([g]) for g in gs[1:]], [1, 2, 3, 4, 6])
    assert e is not None and e["but"] == "inconnu" and d["buts_candidats"] == 0
    assert e["autorisation"] == "experience_uniquement_pas_un_plan"


def test_bp35_archive_debloquee_pas_repetition():
    p = Path(__file__).parent / "runs/roles_autonomes_bp35_fige1/N1/partie"
    z = np.load(p.with_suffix(".npz"))
    gs = list(z["images"])
    acts = [r["action"] for r in json.loads(p.with_suffix(".json").read_text())["rows"]]
    e, d = proposer(gs, acts, [z[f"film_{k}"] for k in range(1, 5)], [3, 4, 6])
    assert e is not None and not d["modele_complet_valide"]
    assert d["controle"]["premiere_divergence"] == 1
    # Ne confond pas une expérience autorisée avec un modèle devenu fidèle.
    assert e["actions"][0] not in acts or isinstance(e["actions"][0], list)


def test_animation_refute_hypothese_sans_effet():
    g = np.zeros((2, 2), int)
    inter = g.copy()
    inter[0, 0] = 1
    h = [{"nom": "aucun_effet_visible_hypothese_nulle", "image": g.tolist(), "fin": False}]
    r = comparer(h, g, [inter, g], [], False)[0]
    assert r["ecart_final"] == 0 and not r["conforme"]


def test_aucune_repetition_si_action_seule_deja_vue():
    g = scene(20, 20)
    e, d = proposer([g, g], [4], [np.array([g])], [4])
    assert e is None and d["candidats_non_repetes"] == 0


def test_clic_disponible_signale_meme_si_table_flèches_ne_le_contient_pas():
    gs = [scene(20, 20), scene(23, 20)]
    _, d = proposer(gs, [4], [np.array([gs[1]])], [3, 4, 6])
    assert "CLICK" in d["actions_offertes"]
    assert d["orientation"]["roles_supposes"]["clic"]


def test_dynamique_sans_but_accepte_un_clic_sans_deplacement():
    gs = [scene(20, 20), scene(23, 20), scene(23, 20)]
    v = PerceptionRoles(gs, [4, 6])
    p = v.programme()
    assert any(r["quand"] == ["=", ["action"], "MOUSE"] for r in p["regles"])


def test_sonde_equilibre_actions_au_lieu_de_rejouer_toujours_left():
    gs = [scene(x, 20) for x in (12, 15, 18, 21, 24)]
    e, _ = proposer(gs, [3, 3, 3, 4], [np.array([g]) for g in gs[1:]], [3, 4])
    assert e["actions"] == [4]
