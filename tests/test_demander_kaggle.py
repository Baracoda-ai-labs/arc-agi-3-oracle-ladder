import json

import chrysalide.qwen.demander as D


class _Rep:
    def json(self):
        return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": {}}


def test_serveur_kaggle(monkeypatch, tmp_path):
    vu = {}

    def post(url, json=None, timeout=None):
        vu.update(url=url, modele=json["model"])
        return _Rep()
    import requests
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(D, "schema", lambda t, d: {})
    monkeypatch.setattr(D, "invite", lambda t, d: "q")
    monkeypatch.setattr(D, "vers_reponse", lambda t, b, d: {"statut": "abstention"})
    monkeypatch.setenv("CHRYS_QWEN_SERVEUR", "sglang")
    monkeypatch.setenv("CHRYS_QWEN_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setenv("CHRYS_QWEN_MODELE", "flashnext")
    monkeypatch.setenv("CHRYS_DOSSIER", str(tmp_path))
    r = D.demander_qwen("x", {}, jeu="kaggle_test", cache=False)
    assert vu == {"url": "http://127.0.0.1:8001/v1/chat/completions", "modele": "flashnext"}
    assert r["serveur"] == "sglang" and r["statut"] == "abstention"
    assert json.loads((tmp_path / "demander_qwen.jsonl").read_text().splitlines()[-1])["modele"] == "flashnext"
