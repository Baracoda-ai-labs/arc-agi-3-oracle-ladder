# SPDX-License-Identifier: MIT-0
"""Garde de l'ensemble verrouillé (B, CCM-238-B) : refus sans drapeau, refus avant le 27, refus des témoins ; aucun fichier
de l'ensemble n'est ouvert par ces tests."""
import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments/verrou"))
import garde as G

AVANT, JOUR = datetime.date(2026, 10, 21), datetime.date(2026, 10, 27)
Z = G.VERROU / "jeux/environment_files/z000"


@pytest.mark.parametrize("cible", [{"chemin": Z}, {"chemin": G.REJETE / "jeux"}, {"chemin": G.VERROU / "verrou_27.tgz"}, {"jeu": "vc33"},
                                   {"jeu": "tu93-2b8b7f61"}, {"chemin": "experiments/arc3/environment_files/cn04/x"}])
def test_refus_sans_drapeau(cible, monkeypatch):
    monkeypatch.delenv("CHRYS_VERROU_27", raising=False)
    with pytest.raises(G.Verrouille):
        G.verifier(**cible, aujourdhui=JOUR)


def test_refus_avant_le_27_meme_avec_drapeau(monkeypatch):
    monkeypatch.setenv("CHRYS_VERROU_27", "1")
    with pytest.raises(G.Verrouille):
        G.verifier(chemin=Z, aujourdhui=AVANT)
    with pytest.raises(G.Verrouille):
        G.controler_scelle(aujourdhui=AVANT)  # refus AVANT toute lecture de l'archive


def test_ouvert_le_27_avec_drapeau(monkeypatch):
    monkeypatch.setenv("CHRYS_VERROU_27", "1")
    G.verifier(chemin=Z, aujourdhui=JOUR)
    G.verifier(jeu="wa30", aujourdhui=JOUR)


def test_jeux_ordinaires_libres(monkeypatch):
    monkeypatch.delenv("CHRYS_VERROU_27", raising=False)
    for jeu in ("dc22", "ls20-abc", "y001"):
        G.verifier(jeu=jeu, aujourdhui=AVANT)
    G.verifier(chemin="experiments/T4/jeux/t4/environment_files/y001", aujourdhui=AVANT)
    G.verifier(chemin=Path.home() / "models/chrysalide3", aujourdhui=AVANT)  # le dépôt n'est pas le dossier verrouillé


def test_ecart_refuse_sans_drapeau(monkeypatch):
    monkeypatch.delenv("CHRYS_ECART", raising=False)
    monkeypatch.setenv("CHRYS_VERROU_27", "1")  # le drapeau du 27 n'ouvre pas le lot à l'écart
    with pytest.raises(G.Verrouille):
        G.verifier(chemin=G.ECART / "jeux/environment_files/e000", aujourdhui=JOUR)


def test_ecart_ouvert_avec_drapeau_sans_date(monkeypatch):
    monkeypatch.setenv("CHRYS_ECART", "1")
    monkeypatch.delenv("CHRYS_VERROU_27", raising=False)
    G.verifier(chemin=G.ECART / "jeux/environment_files/e000", aujourdhui=AVANT)
    with pytest.raises(G.Verrouille):  # CHRYS_ECART n'ouvre pas l'ensemble verrouillé
        G.verifier(chemin=Z, aujourdhui=AVANT)
