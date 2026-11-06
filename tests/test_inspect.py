"""D (CW-357) : inspect_model / inspect_options dans l'outil Python de Franzen — versionnés sur l'état ; option jamais
offerte sur un état périmé ; patch du harnais compatible avec patcher_outils, idempotent ; branche : plan → option."""
import shutil
import subprocess
import sys
from pathlib import Path

from chrysalide.arc3 import branche
from chrysalide.arc3.inspect_franzen import SOURCES, etat_pour_franzen, ligne_tour
from tests.test_evenements import _Solveur

RACINE = Path(__file__).resolve().parents[1]


def _repl(etat, n_hist):
    g = {"history": [None] * n_hist, "chrysalide_etat": etat}
    for src in SOURCES:
        exec(src, g)  # noqa: S102 — comme les fonctions retenues du REPL de Franzen
    return g


def test_fonctions_versionnees():
    etat = {"version": 3, "niveau": 2, "regles": "move(c4,a1,0,-1).", "but": "sortie", "options": [{"actions": ["UP"],
            "length": 1, "reaches": "goal"}]}
    g = _repl(etat, 3)
    assert g["inspect_model"]()["stale"] is False and g["inspect_options"]() == etat["options"]
    g = _repl(etat, 4)  # Franzen a joué depuis : l'option est périmée
    assert g["inspect_model"]()["stale"] is True and g["inspect_options"]() == []
    assert _repl(None, 0)["inspect_model"]() == {"available": False}


def test_branche_plan_devient_option(monkeypatch, tmp_path):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    for k in ("CHRYS_MONITEUR", "CHRYS_MOTEUR", "CHRYS_INSPECT"):
        monkeypatch.setenv(k, "1")
    from chrysalide.arc3.moteur import MoteurC
    s = _Solveur()
    s.history_entries = [1, 2]
    s.analyzer = type("A", (), {})()
    b = branche.creer(s, tmp_path, moteur=MoteurC(budget=1))
    b.plan = {"actions": [{"action": "UP"}, {"action": "LEFT"}], "pas": 0}
    b.infos_m = {"origine": "planifier"}  # but de la théorie, vu (CCM-369-A)
    assert b._jouer_plan() is False and s.n == 0  # rien joué
    b._au_modele()
    e = s.analyzer._chrys_inspect
    assert e["version"] == 2 and e["options"][0]["actions"] == ["UP", "LEFT"] and e["options"][0]["reaches"] == "goal"
    assert ligne_tour(s.analyzer)
    s.history_entries.append(3)  # un coup de plus : l'option ne correspond plus à l'état
    assert etat_pour_franzen(b)["options"] == []


def test_patch_harnais_avec_outils(tmp_path):
    for ordre in (("patcher_inspect.py", "patcher_outils.py"), ("patcher_outils.py", "patcher_inspect.py")):
        h = tmp_path / ordre[0] / "ARC3-Inference"
        shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", h / "inference",
                        ignore=shutil.ignore_patterns("__pycache__"))
        sortie = lambda p, h=h: subprocess.run([sys.executable, str(RACINE / "scripts/arc3" / p), str(h)],
                                               capture_output=True, text=True, check=False)
        for p in ordre:
            assert sortie(p).stdout.strip() == "patché"
        assert sortie("patcher_inspect.py").stdout.strip() == "déjà patché"
        for f in ("agent/tool_agent.py", "agent/python_tool_sandbox.py"):
            compile((h / "inference" / f).read_text(), f, "exec")
        assert "chrysalide_etat" in (h / "inference/agent/python_tool_sandbox.py").read_text()


def test_retenues_par_le_controle_de_franzen():
    """Passage I1 (22/10) : `globals()` faisait rejeter nos fonctions (« unavailable dependencies: globals »). Le contrôle
    de rétention du harnais, avec les noms du bac à sable (globales d'état + fonctions intégrées restreintes), les garde."""
    import importlib.util  # chargé à part : ne pas laisser un paquet « inference » de tiers/ dans sys.modules
    spec = importlib.util.spec_from_file_location(
        "_retenues_franzen", RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference/utils/retained_functions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    prepare_functions = mod.prepare_functions
    disponibles = {"history", "chrysalide_etat", "death_ledger", "len", "list", "print", "dict"}  # pas « globals »
    gardees, rejets = prepare_functions(list(SOURCES), disponibles)
    assert sorted(gardees) == ["inspect_model", "inspect_options"] and rejets == []


def test_but_suppose_jamais_goal():
    """CW-412 (1), CCM-356-A : un plan vers un but DEVINÉ est « guessed_goal », jamais « goal » ; (2) pas de phrase sans
    option."""
    from types import SimpleNamespace
    s = SimpleNamespace(history_entries=[None] * 4)
    opt = {"actions": ["RIGHT", "RIGHT"], "but": True, "version": 4}
    devine = SimpleNamespace(s=s, option=opt, precedents=[], infos_m={"but_suppose": "sortie(c4)", "origine": "but_suppose"})
    vu = SimpleNamespace(s=s, option=opt, precedents=[], infos_m={"but": "sortie(c4)", "origine": "moteur"})
    e = etat_pour_franzen(devine)
    assert e["options"][0]["reaches"] == "guessed_goal" and e["statut_but"] == "guessed" and e["but"] == "sortie(c4)"
    assert etat_pour_franzen(vu)["options"][0]["reaches"] == "goal"
    assert ligne_tour(SimpleNamespace(_chrys_inspect={"options": []})) == []
    assert ligne_tour(SimpleNamespace(_chrys_inspect={"options": [{"actions": []}]})) == []
    assert ligne_tour(SimpleNamespace(_chrys_inspect=e)) != []


def test_copie_du_harnais_sans_paquet_chrysalide(tmp_path):
    """A (22/10, J1) : dans le harnais, seul `inference.chrysalide_arc3` existe. La copie de inspect_franzen.py posée par les patchs
    doit construire une option sans importer `chrysalide` (la copie brute de patcher_inspect levait ModuleNotFoundError dès
    qu'une option existait : bilan_plan de F importé par « from chrysalide.arc3.logique… »). Contrôle F-C2 : vraie copie,
    vrai import, paquet `chrysalide` interdit."""
    h = tmp_path / "ARC3-Inference"
    shutil.copytree(RACINE / "tiers/arc-agi-3-solution/ARC3-Inference/inference", h / "inference",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for p in ("patcher_franzen.py", "patcher_garde.py", "patcher_inspect.py"):
        r = subprocess.run([sys.executable, str(RACINE / "scripts/arc3" / p), str(h)], capture_output=True, text=True, check=False)
        assert r.returncode == 0, (p, r.stderr[-500:])
    assert "from chrysalide.arc3" not in (h / "inference/chrysalide_arc3/inspect_franzen.py").read_text()
    code = (
        "import sys; sys.modules['chrysalide'] = None; sys.path.insert(0, sys.argv[1])\n"
        "from inference.chrysalide_arc3.inspect_franzen import etat_pour_franzen\n"
        "S = type('S', (), {'history_entries': [1]})\n"
        "B = type('B', (), {'s': S(), 'infos_m': {'reserve_plan': None}, 'precedents': [],\n"
        "                   'option': {'version': 1, 'actions': [{'action': 'UP'}], 'but': 'x'}})\n"
        "e = etat_pour_franzen(B()); assert e['options'][0]['actions'] == ['UP'], e; print('ok')\n")
    r = subprocess.run([sys.executable, "-c", code, str(h)], capture_output=True, text=True, check=False, cwd=tmp_path)
    assert r.stdout.strip() == "ok", r.stderr[-800:]


def test_statut_du_but_selon_l_origine():
    """CCM-369-A (ft09) : « planifier » / « plan_langage » = but de la théorie, vu → goal / seen ; origine non tracée →
    guessed_goal par prudence."""
    from types import SimpleNamespace
    s = SimpleNamespace(history_entries=[None] * 2)
    opt = {"actions": ["UP"], "but": True, "version": 2}
    e = etat_pour_franzen(SimpleNamespace(s=s, option=opt, precedents=[], infos_m={"origine": "planifier"}))
    assert e["options"][0]["reaches"] == "goal" and e["statut_but"] == "seen"
    e = etat_pour_franzen(SimpleNamespace(s=s, option=opt, precedents=[], infos_m={"origine": "inconnue"}))
    assert e["options"][0]["reaches"] == "guessed_goal" and e["statut_but"] == "guessed"
