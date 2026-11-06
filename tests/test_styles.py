"""D (CW-285) : sélecteur de styles — chaque style essayé une fois, puis le meilleur ; explorateur = moteur muet ;
réglages remis d'un style à l'autre ; pas de changement au milieu d'un plan ; remise à zéro au niveau suivant."""
import os

import numpy as np

from chrysalide.arc3.styles import Selecteur


def _img(k):
    g = np.zeros((4, 4), int)
    g.flat[k % 16] = 1 + k // 16
    return g


def test_tour_des_styles_puis_le_meilleur(monkeypatch):
    monkeypatch.delenv("CHRYS_CONSENSUS", raising=False)
    s = Selecteur(tranche=4, c=0.0)
    vus = []
    k = 0
    for _ in range(4 * 4):  # 4 styles × 4 coups
        nouveau = s.style == "prudent"  # seul « prudent » découvre des images
        actif = s.moteur_actif(0, _img(k), 0)
        vus.append((s.style, actif))
        k += nouveau
    assert [j["style"] for j in s.journal[:4]] == ["audacieux", "prudent", "explorateur", "reflechi"]
    assert s.style == "prudent"  # UCB sans bonus : le meilleur
    assert os.environ.get("CHRYS_CONSENSUS") == "1"


def test_explorateur_fait_taire_le_moteur_et_reglages_remis(monkeypatch):
    monkeypatch.setenv("CHRYS_TEST_BUTS", "0")
    s = Selecteur(tranche=2, styles=["reflechi", "explorateur"])
    assert os.environ["CHRYS_TEST_BUTS"] == "1"
    s.moteur_actif(0, _img(0), 0)
    assert s.moteur_actif(0, _img(1), 0) is False and s.style == "explorateur"
    assert os.environ["CHRYS_TEST_BUTS"] == "0"  # réglage d'origine remis


def test_pas_de_changement_en_plan_et_niveau_suivant():
    s = Selecteur(tranche=2)
    for i in range(5):
        s.moteur_actif(0, _img(0), 0, en_plan=True)
    assert s.style == "audacieux" and not s.journal
    s.moteur_actif(0, _img(0), 0)
    assert s.journal and s.style == "prudent"
    s.moteur_actif(1, _img(0), 0)
    assert s.niveau == 1 and s.style == "audacieux" and all(t == 0 for t, _ in s.stats.values())
