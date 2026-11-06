"""Même protocole d'action que Franzen ; aucune API de jeu ni inférence modèle."""
import copy
from concurrent.futures import Future
from types import SimpleNamespace

import pytest
from observateur_cpu import cle_instantane
from observateur_harnais import Liaison


class Service:
    def __init__(self, erreur=False, bloque=False):
        self.future, self.jobs, self.ferme, self.erreur, self.bloque = None, [], False, erreur, bloque

    def soumettre(self, hist, ctx):
        if self.erreur:
            raise RuntimeError('erreur observation volontaire')
        self.jobs.append((copy.deepcopy(hist), copy.deepcopy(ctx)))
        self.cle = cle_instantane(hist, ctx)
        self.future = Future()
        if not self.bloque:
            self.future.set_result({'statut': 'test'})
        return {'statut': 'soumis', 'cle': self.cle}

    def lire(self, cle):
        r = self.future.result(); self.future = None
        return {'statut': 'termine', 'proposition': r, 'perime': cle != self.cle, 'droit_action': False}

    def fermer(self):
        self.ferme = True


class Solveur:
    def __init__(self):
        self.x, self.score, self.calls = 0, 0, 0
        self.history = []

    def current_frame(self):
        return SimpleNamespace(grid=[[self.x, self.score]])

    def _execute_action(self, action, *, batch_index, batch_size, generated_tokens=None,
                        flush_viewer_payload=True, automatic=False):
        self.calls += 1
        if action.id.name == 'ERREUR':
            raise ValueError('vrai jeu')
        avant = copy.deepcopy(self.current_frame().grid)
        if action.id.name == 'RESET':
            self.x = 0
        else:
            self.x += 1
        self.score += int(self.x == 3)
        self.payload = {'executed': True, 'action_name': action.id.name, 'score': self.score,
                        'action_data': action.data, 'level_completed': self.x == 3,
                        'animation_chain': [avant, copy.deepcopy(self.current_frame().grid)],
                        'automatic': automatic}
        self.history.append(copy.deepcopy(self.payload))
        return self.payload


def jouer(s, nom='ACTION4', data=None):
    return s._execute_action(SimpleNamespace(id=SimpleNamespace(name=nom), data=data or {}),
                             batch_index=0, batch_size=1)


def test_actions_payloads_et_images_identiques_avec_et_sans_liaison():
    resultats = []
    for actif in (False, True):
        s, obs = Solveur(), Service()
        lien = Liaison(s, obs, 'test', minimum=2, periode=1) if actif else None
        try:
            for a in ['ACTION4', 'ACTION4', 'ACTION4', 'RESET', 'ACTION4', 'ACTION4']:
                assert jouer(s, a) is s.payload
            resultats.append((s.calls, s.history, s.current_frame().grid))
            if actif:
                assert obs.jobs and obs.jobs[0][0]['films'][0] == [[[0, 0]], [[1, 0]]]
                assert not any(j.get('droit_action') for j in lien.journal)
        finally:
            if lien:
                lien.fermer()
    assert resultats[0] == resultats[1]


def test_erreur_observation_ne_rejoue_pas_le_vrai_coup():
    s, obs = Solveur(), Service(erreur=True)
    lien = Liaison(s, obs, 'test', minimum=1, periode=1)
    jouer(s); jouer(s)
    assert s.calls == 2 and not lien.actif and len(s.history) == 2
    lien.fermer()


def test_erreur_vrai_jeu_propagee_une_seule_fois():
    s = Solveur(); lien = Liaison(s, Service(), 'test')
    with pytest.raises(ValueError, match='vrai jeu'):
        jouer(s, 'ERREUR')
    assert s.calls == 1
    lien.fermer()


def test_resultat_apres_reset_perime_et_fenetre_separee():
    s, obs = Solveur(), Service(bloque=True)
    lien = Liaison(s, obs, 'test', minimum=1, periode=1)
    jouer(s)
    jouer(s, 'RESET')
    obs.future.set_result({'statut': 'test'})
    jouer(s)
    assert lien.derniere['perime']
    assert len(obs.jobs[-1][0]['lots']) == 1
    lien.fermer()


def test_clic_conserve_coordonnees_et_pas_de_file():
    s, obs = Solveur(), Service(bloque=True)
    lien = Liaison(s, obs, 'test', minimum=1, periode=1)
    jouer(s, 'ACTION6', {'x': 12, 'y': 7})
    jouer(s)
    assert obs.jobs[0][0]['lots'][0]['actions'][0] == {'action': 'ACTION6', 'row': 7, 'col': 12}
    assert len(obs.jobs) == 1
    lien.fermer()


def test_play_reel_copie_installe_et_ferme_sans_importer_le_serveur(monkeypatch, tmp_path):
    import ast
    import os
    from pathlib import Path

    from preparer_harnais_observateur import transformer
    source = Path(__file__).with_name('harnais_observateur') / 'inference/framework/solver.py'
    # La copie a déjà été transformée ; son play est exécuté seul avec interfaces neutres.
    arbre = ast.parse(source.read_text())
    classe = next(c for c in arbre.body if isinstance(c, ast.ClassDef) and c.name == '_HarnessGameSession')
    play = next(m for m in classe.body if isinstance(m, ast.FunctionDef) and m.name == 'play')
    espace = {'os': os, '_priority_gate': lambda: None, '_analyzer_reported_tokens': lambda a: 0}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[play], type_ignores=[])), '<play-copie>', 'exec'), espace)  # noqa: S102 — méthode du harnais archivé, aucun code LLM
    import observateur_harnais
    for actif in (False, True):
        evenements = []
        liaison = SimpleNamespace(fermer=lambda ev=evenements: ev.append('fermer'))
        monkeypatch.setattr(observateur_harnais, 'installer', lambda s, p, ev=evenements, li=liaison: (ev.append('installer'), li)[1])
        monkeypatch.setenv('CHRYS_OBSERVATEUR_CPU', '1' if actif else '0')
        s = SimpleNamespace(game=SimpleNamespace(game_run=SimpleNamespace(game_id='factice')),
            analysis_html_relpath='analyse', transcript_path=tmp_path / 'trace.txt', analyzer=None,
            seed_initial_history=lambda: None, write_runtime_state=lambda: None,
            _append_initial_viewer_event=lambda: None, write_viewer_payload=lambda: None,
            _play_inner=lambda ev=evenements: ev.append('jouer'))
        espace['play'](s)
        assert evenements == (['installer', 'jouer', 'fermer'] if actif else ['jouer'])
    # Un nouveau patch ne peut pas être appliqué silencieusement sur un fichier déjà patché.
    with pytest.raises(AssertionError):
        transformer(source.read_text())


def test_installation_refuse_ancien_verrou_et_ouvriers_non_bornes(monkeypatch):
    from observateur_harnais import installer
    monkeypatch.setenv('CHRYS_PORTE_V4', '1')
    with pytest.raises(ValueError, match='Observateur seul'):
        installer(Solveur(), 'test')
    monkeypatch.delenv('CHRYS_PORTE_V4')
    monkeypatch.delenv('CHRYS_MOTEUR', raising=False)
    monkeypatch.delenv('CHRYS_MOTEUR_PROCESSUS_DELAI_S', raising=False)
    with pytest.raises(ValueError, match='Delai dur'):
        installer(Solveur(), 'test')
    monkeypatch.setenv('CHRYS_MOTEUR_PROCESSUS_DELAI_S', '15')
    monkeypatch.setenv('CHRYS_MOTEUR_OUVRIERS', '3')
    with pytest.raises(ValueError, match='deux ouvriers'):
        installer(Solveur(), 'test')
