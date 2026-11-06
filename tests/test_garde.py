"""Garde-fou de soumission (garde.py) sur le solveur factice de test_branche : F-C2 sans exception ; repli Franzen sinon."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chrysalide.arc3 import branche, garde
from tests.test_branche import Solveur

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture
def allume(monkeypatch):
    for n in branche.INTERRUPTEURS:
        monkeypatch.setenv(f"CHRYS_{n}", "1")
    monkeypatch.delenv("CHRYS_MOTEUR", raising=False)  # le moteur formel n'a rien à faire sur le jouet
    monkeypatch.delenv("CHRYS_PORTE_V4", raising=False)  # mode à part (tests/test_porte_v4.py)
    monkeypatch.delenv("CHRYS_PORTE5", raising=False)


def _partie(fabrique, s, d):
    b = fabrique(s, d)
    for _ in range(2):
        assert not b.tour()
        s.jouer_modele()
    sans = sum(bool(b.tour()) for _ in range(2))
    return b, sans


def test_fc2_sans_exception_identique_a_la_branche(allume, tmp_path):
    s1, s2 = Solveur(), Solveur()
    b1, n1 = _partie(branche.creer, s1, tmp_path / "b")
    b2, n2 = _partie(garde.creer, s2, tmp_path / "g")
    assert n1 == n2 == 2 and s1.appels_modele == s2.appels_modele == 2
    assert b1.bilan() == b2.bilan() and s2.step_env.__self__ is s2
    t = lambda p: [{k: v for k, v in json.loads(x).items() if k != "t"} for x in (p / "jeu_trace.jsonl").read_text().splitlines()]
    assert t(tmp_path / "b") == t(tmp_path / "g") and not (tmp_path / "g" / "garde.jsonl").exists()


def test_aucun_interrupteur_solveur_intact(monkeypatch):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    s = Solveur()
    orig = s.step_env
    assert garde.creer(s) is None and s.step_env == orig


def test_creer_qui_leve_rend_le_solveur_intact(allume, monkeypatch, tmp_path):
    monkeypatch.setattr(branche, "creer", lambda *a, **k: 1 / 0)
    s = Solveur()
    orig = s.step_env
    assert garde.creer(s, tmp_path) is None and s.step_env == orig
    assert json.loads((tmp_path / "garde.jsonl").read_text())["cause"] == "creer"


def test_tour_qui_leve_repli_franzen(allume, monkeypatch, tmp_path):
    s = Solveur()
    g = garde.creer(s, tmp_path)
    monkeypatch.setattr(g.b, "tour", lambda: 1 / 0)
    assert g.tour() is False and s._chrys is None and g.b is None
    assert s.step_env == Solveur.step_env.__get__(s)  # méthode d'origine remise
    s.jouer_modele()  # Franzen continue
    assert s.appels_modele == 1


def test_suivi_qui_leve_apres_le_coup_ne_rejoue_pas(allume, monkeypatch, tmp_path):
    s = Solveur()
    g = garde.creer(s, tmp_path)
    monkeypatch.setattr(g.b.moniteur, "observer", lambda *a, **k: 1 / 0)  # plante APRÈS le vrai coup
    p = s.step_env({"actions": [{"action": "UP"}]})
    assert p["executed"] and s.n == 1  # coup joué une seule fois, rendu tel quel
    assert s._chrys is None and json.loads((tmp_path / "garde.jsonl").read_text())["cause"] == "step_env"


def test_erreur_du_vrai_coup_remonte(allume, tmp_path):
    s = Solveur()
    garde.creer(s, tmp_path)
    with pytest.raises(KeyError):
        s.step_env({"actions": [{"pas_action": 1}]})  # Franzen lève : on n'avale pas son erreur
    assert not (tmp_path / "garde.jsonl").exists()


def test_plafond_mural(allume, monkeypatch, tmp_path):
    monkeypatch.setenv("CHRYS_GARDE_MUR_S", "0")
    s = Solveur()
    g = garde.creer(s, tmp_path)
    g.tour()
    assert g.b is None and json.loads((tmp_path / "garde.jsonl").read_text())["cause"] == "mur"


def test_patchers_sur_copie_du_harnais(tmp_path):
    h = tmp_path / "ARC3-Inference"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference/framework", h / "inference/framework")
    py = sys.executable
    sortie = lambda p: subprocess.run([py, str(RACINE / "scripts/arc3" / p), str(h)], capture_output=True, text=True, check=False)
    assert sortie("patcher_garde.py").returncode != 0  # avant patcher_franzen : refus
    assert sortie("patcher_franzen.py").stdout.strip() == "patché"
    assert sortie("patcher_garde.py").stdout.strip() == "patché"
    assert sortie("patcher_garde.py").stdout.strip() == "déjà patché"
    s = (h / "inference/framework/solver.py").read_text()
    assert "chrysalide_arc3.garde import creer" in s and "chrysalide_arc3.branche import creer" not in s
    assert "from inference.chrysalide_arc3 import branche" in (h / "inference/chrysalide_arc3/garde.py").read_text()


def test_journal_qui_leve_cles_non_textuelles(allume, tmp_path):
    """CW-179.1 : ls20 g0 tombé sur une écriture de journal (clés non textuelles) → ici, repli et coup rendu."""
    s = Solveur()
    g = garde.creer(s, tmp_path)
    g.b._noter = lambda ligne: json.dumps({(1, 2): ligne})  # TypeError : keys must be str…
    p = s.step_env({"actions": [{"action": "UP"}]})
    assert p["executed"] and s.n == 1 and s._chrys is None
    assert "TypeError" in json.loads((tmp_path / "garde.jsonl").read_text())["erreur"]


def test_journal_qui_leve_pendant_un_coup_sans_modele(allume, tmp_path):
    s = Solveur()
    g = garde.creer(s, tmp_path)
    for _ in range(2):  # niveau 1 joué par le modèle : réflexe appris
        g.tour()
        s.jouer_modele()
    g.b._noter = lambda ligne: json.dumps({(1, 2): ligne})
    assert g.tour() is False and s._chrys is None  # le coup réflexe a planté dans le journal : repli, Franzen reprend
    s.jouer_modele()
    assert s.appels_modele == 3


def test_delai_dur_du_tour_et_calcul_abandonne_muet(allume, monkeypatch, tmp_path):
    """CCM-164-A : un `tour()` qui ne rend pas la main est coupé ; le calcul abandonné ne peut plus jouer."""
    import threading
    import time
    monkeypatch.setenv("CHRYS_GARDE_TOUR_S", "0.2")
    s = Solveur()
    g = garde.creer(s, tmp_path)
    b, fin = g.b, threading.Event()

    def lent():
        time.sleep(0.6)
        try:
            b.step_env({"actions": [{"action": "UP"}]})  # le zombie essaie de jouer après la coupure
        finally:
            fin.set()
    monkeypatch.setattr(b, "tour", lent)
    t0 = time.monotonic()
    assert g.tour() is False and time.monotonic() - t0 < 0.5 and s._chrys is None
    assert json.loads((tmp_path / "garde.jsonl").read_text())["cause"] == "delai_tour"
    s.jouer_modele()  # Franzen reprend tout de suite
    assert fin.wait(2) and s.n == 1 and s.appels_modele == 1  # un seul coup joué : celui du modèle


def test_prise_de_main_sur_stagnation(allume, monkeypatch, tmp_path):
    """CW-261 : avec CHRYS_STAGNATION_COUPS=3, le moteur ne propose rien avant 3 actions sur le niveau ; il observe."""
    monkeypatch.setenv("CHRYS_STAGNATION_COUPS", "3")
    s = Solveur()
    g = garde.creer(s, tmp_path)
    appels = []
    monkeypatch.setattr(g.b, "tour", lambda: appels.append(1) or False)
    assert g.tour() is False and appels == []          # 0 action : Franzen joue
    s.jouer_modele()
    s.step_env({"actions": [{"action": "LEFT"}]})
    s.step_env({"actions": [{"action": "LEFT"}]})        # 3 actions sur le niveau (le moniteur les a vues)
    g.tour()
    assert appels == [1]


def test_apres_victoire_de_franzen_seulement(allume, monkeypatch, tmp_path):
    """CW-332 (c) : avec CHRYS_APRES_VICTOIRE=1, le moteur n'est consulté qu'après un niveau gagné par Franzen lui-même."""
    monkeypatch.setenv("CHRYS_APRES_VICTOIRE", "1")
    s = Solveur()
    g = garde.creer(s, tmp_path)
    appels = []
    monkeypatch.setattr(g.b, "tour", lambda: appels.append(1) or False)
    g.b.evenements = [{"evenement": "coup", "source": "modele"}]
    g.tour()
    assert appels == []                                   # niveau 1 : Franzen apprend seul
    g.b.evenements.append({"evenement": "niveau", "source": "moteur"})
    g.tour()
    assert appels == []                                   # niveau fini par le moteur : Franzen joue le suivant
    g.b.evenements.append({"evenement": "niveau", "source": "modele"})
    g.tour()
    assert appels == [1]                                  # niveau gagné par Franzen : le moteur peut finir plus court


def test_releve_une_decision_au_debut_du_niveau(allume, monkeypatch, tmp_path):
    """CW-401 / CW-412.2 (CHRYS_RELEVE) : au niveau qui suit une victoire de Franzen, le moteur n'est consulté qu'au début ;
    refus ou plan fini → plus aucun appel jusqu'au niveau suivant ; si Franzen a déjà joué sur le niveau, jamais."""
    monkeypatch.setenv("CHRYS_RELEVE", "1")
    s = Solveur()
    g = garde.creer(s, tmp_path)
    appels, reponse = [], {"v": False}
    g.b.m = {"appels": 0}

    def tour():  # un VRAI appel du moteur est compté par la branche (CW-424 : on ne ferme qu'après un appel)
        appels.append(1)
        g.b.m["appels"] += 1
        return reponse["v"]
    monkeypatch.setattr(g.b, "tour", tour)
    g.b.plan = None
    g.b.evenements = [{"evenement": "coup", "source": "modele"}]
    g.tour()
    assert appels == []                                    # niveau 1 : Franzen seul
    g.b.evenements.append({"evenement": "niveau", "source": "modele"})
    g.tour()
    g.tour()
    assert appels == [1]                                   # refus au début : un seul appel sur ce niveau
    g.b.evenements += [{"evenement": "coup", "source": "modele"}, {"evenement": "niveau", "source": "modele"}]
    reponse["v"], g.b.plan = True, {"actions": [1, 2]}
    g.tour()
    g.b.evenements.append({"evenement": "coup", "source": "moteur"})
    g.tour()
    assert appels == [1, 1, 1]                             # plan accepté puis en cours : le moteur continue
    g.b.plan = None                                        # plan fini ou divergence
    g.tour()
    assert appels == [1, 1, 1]                             # la main revient à Franzen pour le reste du niveau
    g.b.evenements += [{"evenement": "coup", "source": "modele"}, {"evenement": "niveau", "source": "moteur"}]
    g.tour()
    assert appels == [1, 1, 1]                             # niveau fini par le moteur : Franzen joue le suivant


def test_releve_vraie_branche_appelle_le_moteur_au_debut_du_niveau(monkeypatch, tmp_path):
    """CW-424 (contrôle F-C2 qui manquait) : VRAIE branche, vraie garde, seul le moteur est factice. Niveau 1 gagné par
    Franzen ; au 1er tour du niveau 2, `proposer` est appelé UNE fois, `lots` vide et `precedents` non vide ; refus →
    plus aucun appel sur ce niveau, même après des coups de Franzen."""
    from tests.test_evenements import _Solveur
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    for k in ("CHRYS_MONITEUR", "CHRYS_MOTEUR", "CHRYS_RELEVE"):
        monkeypatch.setenv(k, "1")

    class Faux:
        porte_propre, infos = False, {}

        def __init__(self):
            self.vus = []

        def proposer(self, h):
            self.vus.append(h)
            self.infos = {"refus": "relève : porte fermée"}

        def classes_inconnues(self, *a):
            return ()
    s = _Solveur()
    g = garde.creer(s, tmp_path)
    g.b.moteur = m = Faux()
    for _ in range(3):  # niveau 1, joué par Franzen (le 3ᵉ coup finit le niveau)
        assert g.tour() is False
        s.step_env({"actions": [{"action": "UP"}]})
    assert m.vus == []                                     # niveau 1 : jamais consulté
    assert g.tour() is False
    assert len(m.vus) == 1 and m.vus[0]["lots"] == [] and len(m.vus[0]["precedents"]) == 1
    g.tour()
    s.step_env({"actions": [{"action": "UP"}]})
    g.tour()
    assert len(m.vus) == 1                                 # refus : plus d'appel sur ce niveau
