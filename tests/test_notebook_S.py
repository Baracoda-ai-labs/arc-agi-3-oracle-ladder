"""Cellule Chrysalide du notebook soumettable (faire_notebook_S.py), exécutée hors Kaggle sur une copie du harnais."""
import json
import os
import shutil
from pathlib import Path

import pytest

from scripts.arc3 import faire_notebook_S as fab

RACINE = Path(__file__).resolve().parents[1]


def _cellule(tmp_path):
    fab.main("S1", tmp_path)  # jamais dans kaggle/ : le livrable n'est fabriqué qu'à la main
    nb = json.loads((tmp_path / "notebook_S1.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and "CHRYSALIDE — variante S1" in "".join(c["source"]))
    bundle = tmp_path / "bundle"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference/framework",
                    bundle / "src/ARC3-Inference/inference/framework")
    (bundle / "src/ARC3-Inference/inference/__init__.py").write_text("")
    (tmp_path / "work").mkdir()
    return src, {"BUNDLE_DIR": bundle, "WORKING_DIR": tmp_path / "work", "CHRYS_ENTREES": str(tmp_path)}


@pytest.fixture(autouse=True)
def env_propre(monkeypatch):
    for k in list(os.environ):
        if k.startswith("CHRYS_"):
            monkeypatch.delenv(k)
    yield
    for k in list(os.environ):
        if k.startswith("CHRYS_"):
            del os.environ[k]


def test_essai_pose_les_interrupteurs(tmp_path):
    src, g = _cellule(tmp_path)
    exec(compile(src, "cellule", "exec"), g | {"TRUE_SUBMISSION": False})  # noqa: S102
    assert os.environ["CHRYS_MOTEUR"] == "1" and os.environ["CHRYS_TUTO"] == "0"
    assert os.environ["CHRYS_DOSSIER"] == str(tmp_path / "work/chrysalide_runs")
    assert "CHRYSALIDE-GARDE" in (g["BUNDLE_DIR"] / "src/ARC3-Inference/inference/framework/solver.py").read_text()


def test_soumission_repli_franzen_pur(tmp_path):
    src, g = _cellule(tmp_path)
    (g["BUNDLE_DIR"] / "src/ARC3-Inference/inference/framework/solver.py").write_text("# autre version\n")  # ancre absente
    exec(compile(src, "cellule", "exec"), g | {"TRUE_SUBMISSION": True})  # noqa: S102 — ne lève pas
    assert not any(k.startswith("CHRYS_") for k in os.environ)
    assert "patcher_franzen" in (tmp_path / "work/CHRYSALIDE_REPLI.txt").read_text()


def test_essai_echec_arrete(tmp_path):
    src, g = _cellule(tmp_path)
    (g["BUNDLE_DIR"] / "src/ARC3-Inference/inference/framework/solver.py").write_text("# autre version\n")
    with pytest.raises(RuntimeError):
        exec(compile(src, "cellule", "exec"), g | {"TRUE_SUBMISSION": False})  # noqa: S102


def test_essai_ecrit_la_telemetrie_cpu(tmp_path):
    src, g = _cellule(tmp_path)
    exec(compile(src, "cellule", "exec"), g | {"TRUE_SUBMISSION": False})  # noqa: S102
    import time
    time.sleep(0.3)
    lignes = (tmp_path / "work/chrysalide_cpu.jsonl").read_text().splitlines()
    assert json.loads(lignes[0])["nproc"] >= 1 and "proc_cpu_s" in json.loads(lignes[1])


def test_variante_f8_flux_et_moteur_eteint(tmp_path, monkeypatch):
    """CW-222 : F8 pose 8 flux (même en repli) et n'allume aucun CHRYS_* (Franzen seul)."""
    monkeypatch.delenv("ARC3_MAX_ACTIVE_STREAMS", raising=False)
    fab.main("F8", tmp_path)
    nb = json.loads((tmp_path / "notebook_F8.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and "CHRYSALIDE — variante F8" in "".join(c["source"]))
    bundle = tmp_path / "bundle"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference/framework",
                    bundle / "src/ARC3-Inference/inference/framework")
    (bundle / "src/ARC3-Inference/inference/__init__.py").write_text("")
    (tmp_path / "work").mkdir()
    exec(compile(src, "cellule", "exec"), {"BUNDLE_DIR": bundle, "WORKING_DIR": tmp_path / "work",  # noqa: S102
                                           "CHRYS_ENTREES": str(tmp_path), "TRUE_SUBMISSION": False})
    assert os.environ["ARC3_MAX_ACTIVE_STREAMS"] == "8"
    assert "CHRYS_MOTEUR" not in os.environ


def test_reglages_en_ligne_de_commande(tmp_path):
    fab.main("S1", tmp_path, "flux=8", "CHRYS_MOTEUR_BUDGET1_S=20")
    p = tmp_path / "notebook_S1_flux8_moteur_budget1_s20.ipynb"
    t = p.read_text()
    assert "_CHRYS_FLUX = 8" in t and "'CHRYS_MOTEUR_BUDGET1_S': '20'" in t


def _cellule_i(tmp_path):
    fab.main("I", tmp_path)
    nb = json.loads((tmp_path / "notebook_I.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and "CHRYSALIDE — variante I" in "".join(c["source"]))
    bundle = tmp_path / "bundle"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", bundle / "src/ARC3-Inference/inference",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "work").mkdir()
    return src, {"BUNDLE_DIR": bundle, "WORKING_DIR": tmp_path / "work", "CHRYS_ENTREES": str(tmp_path),
                 "TRUE_SUBMISSION": True, "SERVER_BASE_URL": "http://127.0.0.1:8001/v1", "SERVED_MODEL_NAME": "flashnext"}


@pytest.mark.parametrize("persistantes", ["1", "0"])
def test_variante_i_inspect(tmp_path, monkeypatch, persistantes):
    """CW-357 voie 2 : INSPECT posé si les fonctions retenues du v3 sont actives ; sinon retiré SEUL (le moteur reste)."""
    monkeypatch.setenv("ARC3_PERSISTENT_FUNCTIONS", persistantes)
    src, g = _cellule_i(tmp_path)
    exec(compile(src, "cellule", "exec"), g)  # noqa: S102
    agent = (g["BUNDLE_DIR"] / "src/ARC3-Inference/inference/agent/tool_agent.py").read_text()
    assert os.environ["CHRYS_MOTEUR"] == "1" and not (tmp_path / "work/CHRYSALIDE_REPLI.txt").exists()
    assert (os.environ.get("CHRYS_INSPECT") == "1") == (persistantes == "1")
    assert "CHRYSALIDE-INSPECT" in agent  # le patch lui-même est inerte sans CHRYS_INSPECT
    assert os.environ["CHRYS_QWEN_SERVEUR"] == "sglang" and os.environ["CHRYS_QWEN_MODELE"] == "flashnext"
    import importlib
    import sys
    sys.modules.pop("chrysalide.qwen.demander", None)
    assert importlib.import_module("chrysalide.qwen.demander").SERVEURS


@pytest.mark.parametrize("persistantes", ["1", "0"])
def test_variante_ro_outils_apres_stagnation(tmp_path, monkeypatch, persistantes):
    """Codex 28/10 : RO = R0 + outils de navigation après 40 coups sans finir le niveau ; moteur jamais allumé ;
    sans fonctions retenues du v3, CHRYS_OUTILS* est retiré SEUL (= R0)."""
    for k in [k for k in os.environ if k.startswith("CHRYS_")]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ARC3_PERSISTENT_FUNCTIONS", persistantes)
    fab.main("RO", tmp_path)
    nb = json.loads((tmp_path / "notebook_RO.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and "CHRYSALIDE — variante RO" in "".join(c["source"]))
    bundle = tmp_path / "bundle"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", bundle / "src/ARC3-Inference/inference",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "work").mkdir()
    g = {"BUNDLE_DIR": bundle, "WORKING_DIR": tmp_path / "work", "CHRYS_ENTREES": str(tmp_path),
         "TRUE_SUBMISSION": True, "SERVER_BASE_URL": "http://127.0.0.1:8001/v1", "SERVED_MODEL_NAME": "flashnext"}
    exec(compile(src, "cellule", "exec"), g)  # noqa: S102
    agent = (bundle / "src/ARC3-Inference/inference/agent/tool_agent.py").read_text()
    assert os.environ.get("CHRYS_MOTEUR") is None and not (tmp_path / "work/CHRYSALIDE_REPLI.txt").exists()
    assert (os.environ.get("CHRYS_OUTILS") == "1") == (persistantes == "1")
    assert (os.environ.get("CHRYS_OUTILS_APRES") == "40") == (persistantes == "1")
    assert "CHRYSALIDE-OUTILS" in agent  # le patch est inerte sans CHRYS_OUTILS (retiré quand persistantes = 0)


_MESSAGE = r"""
import hashlib, json, sys
import inference.agent.tool_agent as ta
from inference.agent.runtime_state import Frame, HistoryEntry
ta.current_grid_image_part = lambda frame: {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,TEST'}}
g0 = tuple(tuple(0 for _ in range(64)) for _ in range(64))
g1 = tuple(tuple(1 if (i, j) == (5, 5) else 0 for j in range(64)) for i in range(64))
h = [HistoryEntry('', Frame(g0, 0, 1))]
for i in range(1, 9):  # 8 actions : ACTION1 sans effet visible, ACTION2 qui change l'image
    a = 1 if i % 2 else 2
    h.append(HistoryEntry(str(a), Frame(g0 if a == 1 else (g1 if i % 4 == 2 else g0), i, 1),
                          {'action_name': f'ACTION{a}', 'automatic': False}))
x = ta.ToolAgent.__new__(ta.ToolAgent)
for k, v in dict(_kept_functions={}, _retained_clear_notice='', _pending_diff_image=None, _pending_diff_image_label='',
                 _pending_animation_image=None, _pending_animation_image_label='', _pending_gameover_images=[],
                 _chrys_faits_history=h).items():
    setattr(x, k, v)
m = x._build_user_message('hello', h[-1].frame)
p = json.dumps(m, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
print(json.dumps({'sha': hashlib.sha256(p).hexdigest(), 'faits': b'OBSERVED FINAL FRAMES' in p}))
"""


def _harnais_variante(tmp_path, nom, monkeypatch):
    for k in [k for k in os.environ if k.startswith("CHRYS_")]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ARC3_PERSISTENT_FUNCTIONS", "1")
    d = tmp_path / nom
    d.mkdir()
    fab.main(nom, d)
    nb = json.loads((d / f"notebook_{nom}.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and f"CHRYSALIDE — variante {nom}" in "".join(c["source"]))
    bundle = d / "bundle"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", bundle / "src/ARC3-Inference/inference",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (d / "work").mkdir()
    g = {"BUNDLE_DIR": bundle, "WORKING_DIR": d / "work", "CHRYS_ENTREES": str(d), "TRUE_SUBMISSION": True,
         "SERVER_BASE_URL": "http://127.0.0.1:8001/v1", "SERVED_MODEL_NAME": "flashnext"}
    exec(compile(src, "cellule", "exec"), g)  # noqa: S102
    return bundle / "src/ARC3-Inference", dict(os.environ)


def _message(harnais, env, **force):
    import subprocess
    import sys
    e = {k: v for k, v in env.items()} | force
    r = subprocess.run([sys.executable, "-c", _MESSAGE], cwd=harnais, env=e | {"PYTHONPATH": str(harnais)},
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_variante_rof_eteinte_egale_ro_allumee_ajoute_les_faits(tmp_path, monkeypatch):
    """ROF (Thomas 29/10) : patch des faits posé APRÈS les outils ; CHRYS_FAITS=0 → message identique à RO (même SHA,
    vrai _build_user_message) ; CHRYS_FAITS=1 au-delà du seuil → bloc de comptes présent ; sous le seuil → identique."""
    ro, env_ro = _harnais_variante(tmp_path, "RO", monkeypatch)
    rof, env_rof = _harnais_variante(tmp_path, "ROF", monkeypatch)
    assert env_rof["CHRYS_FAITS"] == "1" and env_rof["CHRYS_FAITS_APRES"] == "40"
    agent = (rof / "inference/agent/tool_agent.py").read_text()
    assert "CHRYSALIDE-FAITS-VISUELS" in agent and "CHRYSALIDE-OUTILS" in agent
    temoin = _message(ro, env_ro)
    assert not temoin["faits"]
    assert _message(rof, env_rof, CHRYS_FAITS="0") == temoin            # éteint = RO
    assert _message(rof, env_rof, CHRYS_FAITS="1") == temoin            # seuil 40 non atteint (8 coups) = RO
    allume = _message(rof, env_rof, CHRYS_FAITS="1", CHRYS_FAITS_APRES="2")
    assert allume["faits"] and allume["sha"] != temoin["sha"]


_PORTE = r"""
import json, os, sys
sys.path.insert(0, sys.argv[2])
from test_porte_v4 import SolveurReel
from inference.chrysalide_arc3 import garde
s = SolveurReel(sys.argv[1])
g = garde.creer(s, sys.argv[3])
g.tour()
print(json.dumps({'niveaux': s.niv, 'module': garde.__file__}))
"""


def _reglages_abba():
    """Lignes COMMUN + P5 du lanceur de la mesure : la référence, plutôt qu'une seconde liste écrite à la main."""
    s = (RACINE / "scripts/pod/abba_porte5.sh").read_text()
    lire = lambda nom: next(x for x in s.splitlines() if x.startswith(f'{nom}="')).split('"')[1].split()  # noqa: E731
    return dict(x.split("=", 1) for x in lire("COMMUN") + lire("P5") if x != "$COMMUN")


def test_rop5_memes_reglages_que_l_abba_et_vraie_partie(tmp_path, monkeypatch):
    """Cellule ROP5 sur une copie du harnais, puis vraie garde, vraie porte, vrai enfant et vrai g50t, DEPUIS le harnais patché."""
    import subprocess
    import sys
    pytest.importorskip("arc_agi")
    h, env = _harnais_variante(tmp_path, "ROP5", monkeypatch)
    assert "CHRYS_PORTE_V4_PAQUET" in env, (tmp_path / "ROP5/work").iterdir()
    abba = _reglages_abba()
    for k in ("MAX_RUNTIME_MINUTES", "ARC3_SUMMARY_INTERVAL_TOKENS", "CHRYS_PORTE_V4_PAQUET"):  # durée : carnet ; résumé : 0 par défaut ; chemin : embarqué
        abba.pop(k)
    assert {k: env.get(k) for k in abba} == abba
    agent = (h / "inference/agent/tool_agent.py").read_text()
    assert "CHRYSALIDE-FAITS-VISUELS" in agent and "CHRYSALIDE-OUTILS" in agent
    assert (h / "inference/chrysalide_arc3/porte_v5_enfant.py").is_file()
    sortie = tmp_path / "traces"
    sortie.mkdir()
    r = subprocess.run([sys.executable, "-c", _PORTE, "g50t", str(RACINE / "tests"), str(sortie)], cwd=h, capture_output=True, text=True,
                       env=env | {"PYTHONPATH": f"{h}:{RACINE}", "CHRYS_DOSSIER": str(sortie)}, timeout=400)
    assert r.returncode == 0, r.stderr[-800:]
    res = json.loads(r.stdout.strip().splitlines()[-1])
    assert res["niveaux"] == 7 and str(h) in res["module"], res


def test_rop5_paquet_illisible_redevient_ro(tmp_path, monkeypatch):
    for k in [k for k in os.environ if k.startswith("CHRYS_")]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ARC3_PERSISTENT_FUNCTIONS", "1")
    fab.main("ROP5", tmp_path)
    nb = json.loads((tmp_path / "notebook_ROP5.ipynb").read_text())
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and "CHRYSALIDE — variante ROP5" in "".join(c["source"]))
    assert "agent_p1.jouer," in src
    src = src.replace("agent_p1.jouer,", "agent_p1.absent,")  # le contrôle de la cellule échoue pour de vrai, dans le vrai python -I
    bundle = tmp_path / "bundle"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", bundle / "src/ARC3-Inference/inference",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "work").mkdir()
    exec(compile(src, "cellule", "exec"), {"BUNDLE_DIR": bundle, "WORKING_DIR": tmp_path / "work", "CHRYS_ENTREES": str(tmp_path), "TRUE_SUBMISSION": True})  # noqa: S102
    assert os.environ.get("CHRYS_OUTILS") == "1" and os.environ.get("CHRYS_PORTE5") is None
    assert os.environ.get("CHRYS_STAGNATION_COUPS") is None and os.environ.get("CHRYS_PORTE_V4_PAQUET") is None
