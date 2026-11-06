from collections import deque

from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer
from support_planificateur_audit import modele, preparer


def test_desactive_identique_au_modele_existant():
    _, h, cs, z, _, rule = preparer()
    image = z["images"][4]
    base = InterventionsElargies(image, h, cs, [3, 4, 6, 7], horizon=4, scene_factory=lambda im, m: decomposer(im, m)[0])
    new = modele(image, h, cs, rule, False, horizon=4)
    assert base.depart == new.depart
    q = deque([base.depart])
    seen = {base.depart}
    while q:
        s = q.popleft()
        assert base.actions(s) == new.actions(s)
        for a in base.actions(s):
            assert base.pas(s, a) == new.pas(s, a)
            t = base.pas(s, a)
            if t not in seen:
                seen.add(t)
                q.append(t)


def test_cycle_change_etat_de_support_et_compte_deux_coups():
    _, h, cs, z, _, rule = preparer()
    model = modele(z["images"][4], h, cs, rule)
    action = tuple(rule["action"])
    cell = next(iter(model.supports_actifs))
    assert cell in model.depart[1]
    closed = model.pas(model.depart, action)
    assert cell not in closed[1] and closed[0] == model.depart[0] and closed[3] == 1
    opened = model.pas(closed, action)
    assert cell in opened[1] and opened[0] == model.depart[0] and opened[3] == 2
    assert all(x == "continue" for x in closed[2])


def test_pas_fermeture_sur_controle_ni_transfert_hors_champ():
    _, h, cs, z, _, rule = preparer()
    model = modele(z["images"][4], h, cs, rule)
    cell = next(iter(model.supports_actifs))
    s = (cell, model.depart[1], model.depart[2], 1)
    assert tuple(rule["action"]) not in model.actions(s)
    shifted = modele(z["images"][7], h, cs, rule, camera=24)
    assert not shifted.supports_actifs
    assert shifted.refus_supports == ["support_partiellement_hors_champ"]


def test_etat_initial_ferme_et_contexte_refuse():
    from support_planificateur import InterventionsSupports

    _, h, cs, z, _, rule = preparer()
    model = modele(z["images"][3], h, cs, rule)
    cell = next(iter(model.supports_actifs))
    action = tuple(rule["action"])
    assert cell not in model.depart[1]
    opened = model.pas(model.depart, action)
    assert cell in opened[1]
    closed = model.pas(opened, action)
    assert closed[:3] == model.depart[:3] and closed[3] == 2
    wrong = InterventionsSupports(
        z["images"][3],
        h,
        cs,
        [3, 4, 6, 7],
        supports=[rule],
        contexte="autre_contexte",
        horizon=3,
        scene_factory=lambda im, m: decomposer(im, m)[0],
    )
    assert not wrong.supports_actifs and wrong.refus_supports == ["contexte_different"]


def test_controle_native_appele_meme_si_clic_ne_deplace_pas():
    from types import SimpleNamespace

    _, h, cs, z, _, rule = preparer()
    model = modele(z["images"][4], h, cs, rule)
    # Instrumenter les programmes, pas remplacer leur sémantique en production.
    calls = []

    def observe(scene, action):
        calls.append(action)
        scene.issue = "defaite"

    model.programmes = {n: SimpleNamespace(step=observe) for n in model.ids}
    result = model.pas(model.depart, tuple(rule["action"]))
    assert result[0] == model.start
    assert len(calls) == len(cs) and set(result[2]) == {"defaite"}
