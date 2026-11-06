# SPDX-License-Identifier: MIT-0
"""CW-431 (C) : adaptateur Kaggle du paquet moteur seul. (1) un témoin n'est JAMAIS créé : refus avant make(), même
avec un suffixe de version ; (2) configurer() → chaque jeu est créé sur l'Arcade fourni avec la feuille de score ;
(3) ÉQUIVALENCE : l'adaptateur hors ligne, placé avant le paquet, rejoue ar25 et ka59 au coup près (PROTOCOLE.md)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
ADAPT = RACINE / "experiments/kaggle_moteur_seul/adaptateur"


def _adaptateur():
    pytest.importorskip("arc_agi")
    spec = importlib.util.spec_from_file_location("jeux_kaggle", ADAPT / "chrysalide/arc3/logique/jeux.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _FauxArcade:
    def __init__(self):
        self.appels = []

    def make(self, gid, scorecard_id=None):
        self.appels.append((gid, scorecard_id))
        return object()


def test_temoins_refuses_avant_make():
    m = _adaptateur()
    a = _FauxArcade()
    m.configurer(a, "carte")
    try:
        for t in ("vc33", "tu93", "wa30", "s5i5", "cn04", "vc33-1a2b3c4d", "cn04-00000000"):
            with pytest.raises(m.TemoinInterdit):
                m.environnement(t, "")
        assert a.appels == []
        assert not issubclass(m.TemoinInterdit, Exception)  # les `except Exception` de P1 et du pilote ne l'avalent pas
    finally:
        m.configurer(None, None)


def test_configurer_cree_sur_l_arcade_fourni():
    m = _adaptateur()
    a = _FauxArcade()
    m.configurer(a, "carte-1")
    try:
        m.environnement("ar25-0c556536", "")
        assert a.appels == [("ar25-0c556536", "carte-1")]
    finally:
        m.configurer(None, None)


ATTENDUS = {  # rejeu au coup près (PROTOCOLE.md) ; v2 = films + nouveauté de G (ar25 change : 37/23, CCM-324-C)
    ("GEL27_moteur_seul", "ar25"): [39, 27, None], ("GEL27_moteur_seul", "ka59"): [11, 50, 35, 46, 39, None],
    ("GEL27_moteur_seul_v2", "ar25"): [37, 23, None], ("GEL27_moteur_seul_v2", "ka59"): [11, 50, 35, 46, 39, None],
    ("GEL27_moteur_seul_v3", "ar25"): [37, 23, None], ("GEL27_moteur_seul_v3", "ka59"): [11, 50, 35, 46, 39, None],
}
DRAPEAUX = {  # ceux que pose chaque lancer.sh (le pilote du carnet doit poser les mêmes)
    "GEL27_moteur_seul": {},
    "GEL27_moteur_seul_v2": {"CHRYS_FILMS_P1": "3", "CHRYS_G_NOUV": "1", "CHRYS_F_CLE": "bande3"},
    "GEL27_moteur_seul_v3": {"CHRYS_FILMS_P1": "3", "CHRYS_G_NOUV": "1", "CHRYS_F_CLE": "bande3", "CHRYS_P1_MOTEUR": "joue",
                             "CHRYS_BUT_SUPPOSE": "1", "CHRYS_P1_MOTEUR_CPU": "30"},
}


@pytest.mark.parametrize("paquet,jeu", sorted(ATTENDUS))
def test_equivalence_hors_ligne_au_coup_pres(tmp_path, jeu, paquet):
    attendu = ATTENDUS[(paquet, jeu)]
    pytest.importorskip("arc_agi")
    src = RACINE / "experiments/arc3/environment_files" / jeu
    if not src.exists():
        pytest.skip("jeux publics absents")
    jeux = tmp_path / "jeux"
    shutil.copytree(src, jeux / jeu)  # ce jeu seul : aucun témoin n'est copié ni lu
    sortie = tmp_path / "sortie"
    r = subprocess.run([sys.executable, "-B", str(ADAPT / "rejouer.py"), str(jeux), str(sortie), jeu],
                       capture_output=True, text=True, timeout=600, cwd=tmp_path, check=False,
                       env={**os.environ, "PAQUET_GEL27": paquet,  # v2 : films allumés, comme le pose son lancer.sh
                            **DRAPEAUX[paquet]})
    assert r.returncode == 0, r.stderr[-2000:]
    rej = json.loads((sortie / "rejeu.json").read_text())
    assert Path(rej["jeux_py"]).resolve() == (ADAPT / "chrysalide/arc3/logique/jeux.py").resolve()  # l'adaptateur a joué
    if paquet.endswith("_v3"):  # v3 : MoteurC doit venir du paquet, pas du dépôt
        assert rej.get("moteur_py", "").startswith(str((RACINE / "experiments" / paquet).resolve())), rej.get("moteur_py")
    assert rej["jeux"][jeu] == attendu
