"""Contre-exemple minimal, sans source ni identifiant de jeu."""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / 'paquet'))

import pytest

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile


def exemple():
    monde = ((3, frozenset({(0, 0)}), 3, 1),)
    th = Theorie(moves={(3, 4): (1, 0)}, retour=((3, 2, 1, 1),))
    th.sans_effet = frozenset({th.cle_sans_effet(monde, 2, (8, 6))})
    return th, monde


def positions(monde):
    return [(o[2], o[3]) for o in monde]


@pytest.mark.parametrize('classe', [Programme, ProgrammeCompile])
@pytest.mark.parametrize('drapeau', ['0', '1'])
def test_sans_effet_supprime_aussi_le_retour(monkeypatch, classe, drapeau):
    monkeypatch.setenv('CHRYS_EXPORT_SANS_EFFET', drapeau)
    th, monde = exemple()
    texte, non = exporter(th, (8, 6))
    assert not non
    scene = Scene((6, 8), 0, 0, [_sprite(o) for o in monde])
    programme = classe(texte)
    programme.step(scene, ('DOWN',))
    attendu = positions(th.pas(monde, 2, (8, 6))[0]) if drapeau == '1' else [(1, 1)]
    assert [(s['x'], s['y']) for s in scene.sprites] == attendu


@pytest.mark.parametrize('classe', [Programme, ProgrammeCompile])
def test_autre_position_garde_le_retour(monkeypatch, classe):
    monkeypatch.setenv('CHRYS_EXPORT_SANS_EFFET', '1')
    th, monde = exemple()
    monde = ((3, monde[0][1], 4, 1),)
    texte, non = exporter(th, (8, 6))
    assert not non
    sc = Scene((6, 8), 0, 0, [_sprite(o) for o in monde])
    classe(texte).step(sc, ('DOWN',))
    assert [(s['x'], s['y']) for s in sc.sprites] == positions(th.pas(monde, 2, (8, 6))[0]) == [(1, 1)]


def test_drapeau_eteint_export_identique(monkeypatch):
    th, _ = exemple()
    monkeypatch.delenv('CHRYS_EXPORT_SANS_EFFET', raising=False)
    sans, _ = exporter(th, (8, 6))
    monkeypatch.setenv('CHRYS_EXPORT_SANS_EFFET', '0')
    eteint, _ = exporter(th, (8, 6))
    assert sans == eteint


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q', '-p', 'no:cacheprovider']))
