"""D (CW-431) : pilote du carnet Kaggle « moteur seul » — garde absolue des 5 témoins, feuille de score toujours fermée,
budget du carnet, un jeu qui plante n'arrête pas les autres."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pilote", RACINE / "experiments/kaggle_moteur_seul/pilote.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class Arcade:
    def __init__(self, ids):
        self.available_environments = [SimpleNamespace(game_id=g) for g in ids]
        self.ouvertes, self.fermees = [], []

    def create_scorecard(self):
        self.ouvertes.append("sc1")
        return "sc1"

    def close_scorecard(self, sc):
        self.fermees.append(sc)


def test_temoins_jamais_joues(tmp_path):
    a = Arcade(["ar25-1", "vc33-9", "ft09-2", "cn04-x", "tu93-1", "wa30-1", "s5i5-1"])
    joues = []
    P.lancer(a, lambda g: joues.append(g) or {"niveaux": 1}, tmp_path, t0=0.0, horloge=lambda: 1.0)
    assert joues == ["ar25-1", "ft09-2"] and a.fermees == ["sc1"]
    with pytest.raises(RuntimeError, match="GARDE TÉMOINS"):
        P.garde(["ar25-1", "vc33-0"])


def test_feuille_fermee_meme_si_tout_plante(tmp_path):
    a = Arcade(["ar25-1", "ft09-2"])
    r = P.lancer(a, lambda g: 1 / 0, tmp_path, t0=0.0, horloge=lambda: 1.0)
    assert [x["jeu"] for x in r] == ["ar25-1", "ft09-2"] and all("ZeroDivisionError" in x["erreur"] for x in r)
    assert a.fermees == ["sc1"]
    a2 = Arcade(["ar25-1"])
    with pytest.raises(KeyboardInterrupt):
        P.lancer(a2, lambda g: (_ for _ in ()).throw(KeyboardInterrupt()), tmp_path, t0=0.0, horloge=lambda: 1.0)
    assert a2.fermees == ["sc1"]


def test_budget_du_carnet(tmp_path):
    a = Arcade(["a-1", "b-1", "c-1"])
    t = {"v": 0.0}

    def jouer(g):
        t["v"] += 16000.0  # chaque jeu prend 16 000 s : le 3ᵉ ne doit pas partir (32 400 − 1 800)
        return {}
    r = P.lancer(a, jouer, tmp_path, t0=0.0, horloge=lambda: t["v"])
    assert [x.get("saute") for x in r] == [None, None, "budget du carnet"]


def test_delai_par_jeu_coupe_et_continue(tmp_path):
    import time as _t
    a = Arcade(["a-1", "b-1"])

    def jouer(g):
        if g == "a-1":
            while True:  # boucle infinie, avec un « except Exception » comme dans P1 : ne doit pas avaler la coupure
                try:
                    _t.sleep(0.05)
                except Exception:  # noqa: BLE001, S110
                    pass
        return {"niveaux": 2}
    r = P.lancer(a, jouer, tmp_path, t0=_t.time(), delai_jeu_s=1)
    assert r[0]["erreur"] == "durée maximale du jeu atteinte" and r[1]["niveaux"] == 2 and a.fermees == ["sc1"]


def test_temoin_dans_un_jeu_arrete_tout(tmp_path):
    """L'exception de garde de l'adaptateur (BaseException) n'est jamais avalée par le pilote."""
    class TemoinInterdit(BaseException):
        pass
    a = Arcade(["a-1", "b-1"])
    with pytest.raises(TemoinInterdit):
        P.lancer(a, lambda g: (_ for _ in ()).throw(TemoinInterdit()), tmp_path, t0=0.0, horloge=lambda: 1.0)
    assert a.fermees == ["sc1"]


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_carnet_de_bout_en_bout_hors_ligne(tmp_path, version):
    """La VRAIE cellule du carnet, exécutée hors ligne sur 2 jeux publics non témoins (ar25, ft09) : paquet vérifié,
    adaptateur chargé avant agent_p1, feuille de score, niveaux gagnés, submission.parquet. Seul le pip est retiré."""
    import json
    import os
    import shutil
    import subprocess as sp
    import sys
    pytest.importorskip("arc_agi")
    spec2 = importlib.util.spec_from_file_location("fab", RACINE / "scripts/arc3/faire_notebook_moteur_seul.py")
    fab = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(fab)
    _nb, code, n = fab.carnet(version)
    assert n >= 60 and f"moteur seul {version}" in code
    attendu = {"v1": {}, "v2": {"CHRYS_FILMS_P1": "3", "CHRYS_G_NOUV": "1", "CHRYS_F_CLE": "bande3"}}
    attendu["v3"] = {**attendu["v2"], "CHRYS_P1_MOTEUR": "joue", "CHRYS_BUT_SUPPOSE": "1", "CHRYS_P1_MOTEUR_CPU": "30"}
    assert fab.env_du_paquet(version) == attendu[version]  # v3 : plusieurs drapeaux sur une ligne « export »
    roues = tmp_path / "comp" / "arc_agi_3_wheels"
    roues.mkdir(parents=True)
    env = tmp_path / "comp" / "environment_files"
    env.mkdir()
    for j in ("ar25", "ft09"):
        shutil.copytree(RACINE / "experiments/arc3/environment_files" / j, env / j)  # l'Arcade ne suit pas les liens
    code = code.replace('Path("/kaggle/working")', f'Path("{tmp_path / "work"}")').replace(
        '"/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels"', f'"{roues}"')
    code = code.replace("subprocess.check_call(", "(lambda *a, **k: 0)(")
    code = code.replace("    import pandas as pd\n", "    import pandas as pd\n    pd.DataFrame.to_parquet = lambda self, p, **k: "
                        "open(p, 'wb').write(b'PAR1')  # pas de pyarrow sur le Mac ; présent sur Kaggle\n")
    (tmp_path / "work").mkdir()
    (tmp_path / "cellule.py").write_text(code)
    r = sp.run([sys.executable, "-B", str(tmp_path / "cellule.py")], capture_output=True, text=True, timeout=600,
               env={k: v for k, v in os.environ.items() if k != "KAGGLE_IS_COMPETITION_RERUN"}, check=False)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-3000:]
    assert "paquet conforme" in r.stdout and "jeux joués 2 / 2" in r.stdout, r.stdout
    lignes = [json.loads(x) for x in (tmp_path / "work/moteur_seul/pilote.jsonl").read_text().splitlines()]
    assert [x["jeu"][:4] for x in lignes] == ["ar25", "ft09"] and lignes[0]["coups"][:2] == {"v1": [39, 27], "v2": [37, 23], "v3": [37, 23]}[version], lignes  # = contrôles de C
    assert (tmp_path / "work/submission.parquet").exists()
    if version == "v3":
        assert "MoteurC chargé depuis" in r.stdout and "paquet" in r.stdout.split("MoteurC chargé depuis")[1].split()[0]
