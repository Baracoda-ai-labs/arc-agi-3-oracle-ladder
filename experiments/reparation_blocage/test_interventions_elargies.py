from types import SimpleNamespace

import numpy as np
from experience_bfws import ExperienceLocale
from interventions_elargies import InterventionsElargies
from proposeur_petites_regles import regle
from test_proposeur_petites_regles import scene

from chrysalide.langue import vers_python


def test_prepare_bloc_distant_sans_inventer_destructibilite():
    m = SimpleNamespace(pas=1, position=lambda im: (0, 0))
    h = SimpleNamespace(
        modele=m, actives=lambda: ["h"], catalogue={"h": (0, True)}, scene=lambda im: ((0, 0), (0, 0), {(0, 0), (1, 0)}, {(2, 0)})
    )
    cs = {"h": {"python": vers_python(regle("controle", "cible", "contact_moteur", "perdre"))}}
    kwargs = {"scene_factory": lambda im, m: scene(5)}
    base = ExperienceLocale(np.zeros((64, 64)), h, cs, [4, 6], **kwargs)
    wide = InterventionsElargies(np.zeros((64, 64)), h, cs, [4, 6], **kwargs)
    click = ("clic", 2, 0)
    assert click not in base.actions(base.depart) and click in wide.actions(wide.depart)
    after = wide.pas(wide.depart, click)
    assert (2, 0) in after[1] and after[0] == (0, 0)
    assert wide.pas(after, 4)[0] == (1, 0)
    assert wide.pas(wide.pas(after, 4), 4)[0] == (2, 0)


def test_cache_conserve_les_issues_de_la_projection_native():
    m = SimpleNamespace(pas=1, position=lambda im: (0, 0))
    h = SimpleNamespace(
        modele=m,
        actives=lambda: ["h"],
        catalogue={"h": (0, False)},
        scene=lambda im: ((0, 0), (0, 0), {(0, 0), (1, 0), (2, 0)}, set()),
    )
    cs = {x: {"python": vers_python(regle("controle", "cible", x, "perdre"))} for x in ("contact_moteur", "proximite_boites")}
    args = (np.zeros((64, 64)), h, cs, [3, 4])
    kw = {"scene_factory": lambda im, m: scene(3)}
    base = ExperienceLocale(*args, **kw)
    wide = InterventionsElargies(*args, **kw)
    a, b = base.depart, wide.depart
    for action in (4, 3, 4, 4):
        a = base.pas(a, action)
        b = wide.pas(b, action)
        assert a == b


def test_enveloppe_trouve_un_desaccord_accessible():
    from enveloppe_contacts import analyser

    m = SimpleNamespace(pas=1, position=lambda im: (0, 0))
    h = SimpleNamespace(
        modele=m,
        actives=lambda: ["h"],
        catalogue={"h": (0, False)},
        scene=lambda im: ((0, 0), (0, 0), {(0, 0), (1, 0), (2, 0)}, set()),
    )
    cs = {x: {"python": vers_python(regle("controle", "cible", x, "perdre"))} for x in ("contact_moteur", "proximite_boites")}
    model = InterventionsElargies(np.zeros((64, 64)), h, cs, [3, 4], scene_factory=lambda im, m: scene(3))
    r = analyser(model)
    assert r["statut"] == "separation_dans_enveloppe" and r["separateurs"]


def test_bootstrap_frontiere_sur_films_archives(tmp_path):
    from experience_frontiere_bp35 import scenes_film
    from preflight_interventions_bp35 import charger
    from apprentissage_regles import Apprentissage
    from issues_observees import issue_sdk
    m, h, cs, z, rows, known = charger()
    learner = Apprentissage([{"id": n, **c} for n, c in cs.items()], tmp_path / "memory.json")
    for i, row in enumerate(rows):
        learner.observer(scenes_film(z["images"][i], z[f"film_{i+1}"], m), issue_sdk(row["state"], row["levels_completed"], 1), str(i))
    assert set(learner.actives(True)) == set(cs)
