"""Éteint et activé sur la même trace ; aucun environnement de jeu chargé."""
import copy
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]

from agent_p1.releve_moteur import tenter


def test_releve_compilee_garde_les_quatre_actions_reference(monkeypatch):
    base = ICI.parents[2] / 'audit/chrysalide_audit_23-10/traces/enregistrements/y056'
    meta = json.loads((base / 'journal_jeu.jsonl').read_text().splitlines()[0])
    rows = json.loads((base / 'N1/partie.json').read_text())['rows']
    images = np.load(base / 'N1/partie.npz')['images']
    for k in list(os.environ):
        if k.startswith('CHRYS_'):
            monkeypatch.delenv(k)
    for k, v in meta['env'].items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv('CHRYS_P1_MOTEUR_CPU', '2')
    monkeypatch.setenv('CHRYS_EXPORT_SANS_EFFET', '1')
    monkeypatch.setenv('CHRYS_CENTRES_RAPIDES', '1')
    resultats = []

    class Lab:
        level = 1
        won = False
        finished = False
        source_observation = 'trace'

        def __init__(self):
            self.rows = copy.deepcopy(rows[:80])
            self.images = [g.copy() for g in images[:81]]
            self.image = self.images[-1]
            self.actions = []

        def play(self, a, origine):
            k = len(self.rows)
            assert a == rows[k]['action']
            self.actions.append(a)
            self.rows.append(copy.deepcopy(rows[k]))
            self.image = images[k + 1].copy()
            self.images.append(self.image)
            self.won = len(self.rows) == 84

    for flag in ['0', '1', 'integree']:
        monkeypatch.setenv('CHRYS_CHAINE_COHERENTE', '1' if flag == 'integree' else flag)
        monkeypatch.setenv('CHRYS_CHAINE_ATMS', '1' if flag == 'integree' else '0')
        monkeypatch.setenv('CHRYS_CHAINE_CEGAR', '1' if flag == 'integree' else '0')
        lab = Lab()
        ex = SimpleNamespace(lab=lab, j=SimpleNamespace(ecrire=lambda *args, **kwargs: None))
        resultat = tenter(ex, 'joue')
        assert resultat == 'victoire_moteur'
        assert len(lab.actions) == 4 and ex.t1_coups == 4
        resultats.append(lab.actions)
        if flag in ('1', 'integree'):
            assert ex.chaine.journal[-1]['statut'] == 'victoire_verifiee_sur_trace'
        if flag == 'integree':
            assert ex.chaine.atms is not None
    assert resultats[0] == resultats[1] == resultats[2]
