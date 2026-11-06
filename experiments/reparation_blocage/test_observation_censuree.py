from types import SimpleNamespace

import observation_censuree as obs


def test_absence_controle_non_terminale_ne_refute_pas(monkeypatch):
    monkeypatch.setattr(obs, "scene_image", lambda *a: SimpleNamespace(sprites=[]))
    assert not obs.issue_pour_revision(None, None, "NOT_FINISHED", 2, 2)["revisable"]
    assert obs.issue_pour_revision(None, None, "GAME_OVER", 2, 2)["issue"] == "defaite"
    assert obs.issue_pour_revision(None, None, "NOT_FINISHED", 3, 2)["issue"] == "niveau"
