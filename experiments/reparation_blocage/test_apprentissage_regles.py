from apprentissage_regles import Apprentissage
from proposeur_petites_regles import regle
from test_proposeur_petites_regles import scene

from chrysalide.langue import vers_python


def candidats():
    return [
        {"id": e, "python": vers_python(regle("controle", "cible", "contact_moteur", e))}
        for e in ("perdre", "gagner", "niveau_suivant")
    ]


def test_apprend_effet_sans_recevoir_regle_cible(tmp_path):
    a = Apprentissage(candidats(), tmp_path / "facts.json")
    a.observer([scene(9)], "continue", "negatif")
    assert len(a.actives()) == 3 and not a.actives(True)
    a.observer([scene(9), scene(0)], "defaite", "positif")
    assert a.actives(True) == ["perdre"]
    assert a.memoire.get("perdre", "regle_candidate")["valeur"]["statut_epistemique"] == "hypothese_soutenue_sur_traces"
    a.observer([scene(0)], "defaite", "nouveau", True, {"perdre": "defaite"})
    assert a.memoire.get("perdre", "regle_candidate")["valeur"]["statut_epistemique"] == "prediction_confirmee_localement"
    a.observer([scene(0)], "continue", "contreexemple")
    assert not a.actives() and a.memoire.get("perdre", "regle_candidate") is None


def test_absence_activation_ne_prouve_pas_absence_autre_cause(tmp_path):
    a = Apprentissage(candidats(), tmp_path / "facts.json")
    a.observer([scene(9)], "defaite", "cause_absente")
    assert len(a.actives()) == 3 and not a.actives(True)


def test_pas_confirmation_retroactive(tmp_path):
    a = Apprentissage(candidats(), tmp_path / "facts.json")
    r = a.observer([scene(0)], "defaite", "nouveau", True, {"perdre": "continue"})
    assert not any(x["confirmation_prospective"] for x in r["decisions"])


def test_extension_distance_natives_et_pas_de_soutien_sans_positif(tmp_path):
    from raffinement_distance import etendre

    c = {"id": "base", "controle": "controle", "cible": "cible", "relation": "proximite_boites", "effet": "perdre"}
    extended = etendre([c], [1, 2])
    a = Apprentissage(extended, tmp_path / "facts.json")
    a.observer([scene(2)], "continue", "negatif")
    assert not a.actives(True)
    assert not a.actives()


def test_choix_interdit_couple_etat_action_deja_joue():
    import numpy as np
    from experience_regles_bp35 import choisir, cle

    image = np.zeros((64, 64), dtype=int)

    def e(action, outcome):
        return {"actions": [action], "predictions": {"a": [(outcome,)], "b": [("continue",)]}}

    ancien = ["clic", 2, 3]
    resultat = choisir([e(ancien, "mort"), e(3, "continue")], ["a", "b"], image, {cle(image, ancien)})
    assert resultat["action"] == 3
    assert choisir([e(ancien, "mort")], ["a", "b"], image, {cle(image, ancien)}) is None


def test_memoire_conserve_portee_famille(tmp_path):
    context = {"famille": "navigation_gravite_clic", "transfert_autorise": False}
    a = Apprentissage(candidats(), tmp_path / "facts.json", context)
    a.observer([scene(0)], "defaite", "film")
    assert a.memoire.get("perdre", "regle_candidate")["valeur"]["contexte"] == context


def test_clic_numpy_equivaut_clic_json_et_ne_peut_etre_rejoue():
    import json

    import numpy as np
    from experience_regles_bp35 import choisir, cle

    im = np.zeros((64, 64), dtype=int)
    old = ["clic", 21, 33]
    new = ["clic", np.int64(21), np.int64(33)]
    assert cle(im, old) == cle(im, new)
    e = {"actions": [new], "predictions": {"a": [("mort",)]}}
    assert choisir([e], ["a"], im, {cle(im, old)}) is None
    result = choisir([e], ["a"], im, set())
    json.dumps(result)


def test_bfws_existant_trouve_sequence_separatrice():
    from experience_bfws import techniques

    plan = techniques().bfws(0, lambda s, a: s + a, [1], lambda s: s == 3, max_noeuds=10)
    assert plan == [1, 1, 1]


def test_adaptateur_bfws_separe_deux_clauses_et_borne_profondeur(monkeypatch):
    from types import SimpleNamespace

    import experience_bfws as module
    import numpy as np
    from proposeur_petites_regles import regle

    monkeypatch.setattr(module, "scene_image", lambda image, m: scene(3))
    m = SimpleNamespace(pas=1, position=lambda image: (0, 0))
    h = SimpleNamespace(
        modele=m,
        actives=lambda: ["h"],
        catalogue={"h": (0, False)},
        scene=lambda image: ((0, 0), (0, 0), {(0, 0), (1, 0), (2, 0)}, set()),
    )
    cs = {x: {"python": vers_python(regle("controle", "cible", x, "perdre"))} for x in ("contact_moteur", "proximite_boites")}
    model = module.ExperienceLocale(np.zeros((64, 64)), h, cs, [4])
    result = model.chercher(max_noeuds=10)
    assert result["plan"] == [4, 4]
    assert len(set(result["etapes"][-1]["predictions"].values())) == 2
    assert not module.ExperienceLocale(np.zeros((64, 64)), h, cs, [4], horizon=1).chercher(max_noeuds=10)["plan"]
