"""Raccordement des preuves filmiques et transport visuel, sans appel IA ni SDK."""
import base64
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / 'paquet'))

from evidence_films import Films


def exemple():
    a = np.zeros((16, 16), dtype=int)
    a[4:7, 2:5] = 3
    b = np.zeros_like(a)
    b[4:7, 8:11] = 3
    return a, np.asarray([b, a])


def test_image_finale_identique_ne_supprime_pas_le_film():
    a, frames = exemple()
    f = Films()
    f.ajouter(a, frames)
    info = f.analyser(0)
    assert not info['preuve']['final_state_changed']
    assert info['preuve']['transient_events_observed']
    assert info['information_temporelle']


def test_extraction_incrementale_pas_quadratique():
    a, frames = exemple()
    f = Films()
    f.ajouter(a, frames)
    assert f.extractions == 0
    assert f.analyser(0) == f.analyser(0)
    assert f.extractions == 1
    f.ajouter(a, frames)
    f.analyser(1)
    assert f.extractions == 1
    f.ajouter(a, None)
    assert f.analyser(2)['statut'] == 'film_absent'


def test_planches_conservent_toutes_les_images_et_le_repere():
    a, frames = exemple()
    f = Films()
    f.ajouter(a, frames)
    pages = f.planches(0, par_page=2)
    assert len(pages) == 2  # Avant + deux images ; aucune image ignorée.
    assert Image.open(io.BytesIO(pages[0])).size == (768, 288)
    assert Image.open(io.BytesIO(pages[1])).size == (512, 288)


def test_connecteur_existant_transmet_effectivement_les_images(monkeypatch):
    import requests

    from chrysalide.qwen.demander import _appel
    a, frames = exemple()
    f = Films()
    f.ajouter(a, frames)
    pages = f.planches(0)

    def post(url, *, json, timeout):
        assert url.endswith('/api/chat')
        assert json['model'] == 'qwen3.8:27b-mlx'
        assert json['options']['num_ctx'] == 16384
        recues = json['messages'][0]['images']
        assert [base64.b64decode(x) for x in recues] == pages
        return SimpleNamespace(json=lambda: {'message': {'content': '{"python":"REPONSE = Abstention(raison=\"test\")"}'},
                                            'done_reason': 'stop'})

    monkeypatch.setattr(requests, 'post', post)
    texte, fin, _ = _appel('ollama', 'qwen3.8:27b-mlx', 'test de transport', {'type': 'object'},
                          64, 120, 0, pages, num_ctx=16384)
    assert fin == 'stop' and 'Abstention' in texte
