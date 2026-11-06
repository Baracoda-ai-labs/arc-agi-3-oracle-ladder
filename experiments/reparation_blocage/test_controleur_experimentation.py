import copy

import numpy as np
import pytest
from controleur_experimentation import Controleur, Dossier
from test_propositions_python import EXP, deux_modeles


def dossier(chaines, reserve=4):
    c = next(iter(chaines.values()))
    return Dossier(c.grilles, [4], [[c.grilles[1]]], ["continue"], 1, reserve, (4,))


def test_question_discriminante_reutilise_chaine_et_proposition():
    cs = deux_modeles()
    d = dossier(cs)
    r = Controleur().decider(d, cs, [EXP])
    assert r["statut"] == "experience_conditionnelle"
    assert r["experience"]["evaluation"]["groupes"] == 2
    assert r["experience"]["cout_coups_prefixe"] == 1
    assert r["risque"] == "inconnu" and not r["droit_action"]


def test_un_modele_n_efface_pas_inconnue():
    cs = deux_modeles()
    cs.pop("bloque")
    r = Controleur().decider(dossier(cs), cs, [EXP])
    assert r["statut"] == "hypothese_manquante" and "issues" in r["incertitudes"]
    assert r["experience"] is None


def test_aucun_gain_information_sur_hypotheses_identiques():
    cs = deux_modeles()
    cs["bloque"] = copy.deepcopy(cs["libre"])
    r = Controleur().decider(dossier(cs), cs, [EXP])
    assert r["statut"] == "hypothese_manquante"
    assert any(e.get("statut") == "sans_information_visible" for e in r["evaluations"])


def test_budget_nul_interdit_experience():
    cs = deux_modeles()
    r = Controleur().decider(dossier(cs, 0), cs, [EXP])
    assert r["experience"] is None


def test_terminal_reste_terminal():
    cs = deux_modeles()
    d = dossier(cs)
    d.issues = ["defaite"]
    assert Controleur().decider(d, cs, [EXP])["statut"] == "episode_termine"


def test_refuse_historique_incoherent_et_preserve_donnees():
    cs = deux_modeles()
    d = dossier(cs)
    before = d.signature()
    Controleur().decider(d, cs, [EXP])
    assert before == d.signature()
    d.images = [np.zeros((64, 64)), np.zeros((64, 64))]
    with pytest.raises(ValueError, match="préfixes distincts"):
        Controleur().decider(d, cs)


def test_films_intermediaires_participent_signature():
    cs = deux_modeles()
    d = dossier(cs)
    other = dossier(cs)
    other = Dossier(other.images, other.actions, [[np.zeros((64, 64)), other.images[1]]], other.issues, 1, 4)
    assert d.signature() != other.signature()


def test_plan_pas_confirme_si_couverture_contredite():
    cs = deux_modeles()
    cs.pop("bloque")
    r = Controleur().decider(
        dossier(cs),
        cs,
        couverture={"perception": "compatible", "mouvement": "compatible", "contact": "compatible", "issues": "contredite"},
    )
    assert r["statut"] == "hypothese_manquante"


def test_memes_images_action_differente_refusee():
    cs = deux_modeles()
    d = dossier(cs)
    d.actions = [3]
    with pytest.raises(ValueError, match="préfixes distincts"):
        Controleur().decider(d, cs)
