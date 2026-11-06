# SPDX-License-Identifier: MIT-0
"""D (CW-139/161) : fabrique kaggle/notebook_<V>.ipynb, notebook SOUMETTABLE « agent Franzen + notre moteur », à partir du
notebook Franzen v3. Une seule cellule ajoutée (après la cellule qui rend le harnais importable) :
- écrit EN CLAIR tout chrysalide/arc3 (+ patcher_franzen.py, patcher_garde.py), applique les deux patchs au harnais ;
- installe clingo hors ligne depuis une roue trouvée sous /kaggle/input (dataset « chrysalide-roues », kaggle/roues/) ;
- essai à blanc : clingo résout, garde/branche/moteur s'importent, MoteurCle se construit ;
- pose les interrupteurs CHRYS_* de la variante. En SOUMISSION, tout échec → interrupteurs éteints = Franzen pur
  (le score n'est pas perdu ; /kaggle/working/CHRYSALIDE_REPLI.txt) ; en ESSAI, tout échec arrête le notebook.
Cellule de réglages : en essai (Save & Run All, non soumis), ESSAI = 3 jeux publics, 1 passe, 48 min par jeu
(≈ temps de flux par jeu de la soumission : 532 min × 10 flux / 110 jeux) ; en soumission, réglages de Franzen inchangés.
Usage : uv run python scripts/arc3/faire_notebook_S.py [S1|S1b|S0|F8|S1F8] [flux=N] [CHRYS_X=val …]"""
import ast
import base64
import copy
import hashlib
import json
import lzma
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "tiers/franzen_notebook/arc-agi-3-milestone-2-solution_v3.ipynb"
COMMUN = {"CHRYS_MOTEUR": "1", "CHRYS_MOTEUR_CLE": "1", "CHRYS_TUTO": "0",  # CCM-106-B : tutoriel éteint le 19/10
          "CHRYS_MOTEUR_BUDGET_S": "2", "CHRYS_MOTEUR_BUDGET1_S": "30",  # CW-183 (E2E4 : 22 min de CPU sur 60) : budgets serrés
          "CHRYS_MOTEUR_CPU_JEU_S": "60",  # CCM-154-A : au-delà de 60 s de CPU moteur dans un jeu, Franzen seul
          "CHRYS_GARDE_MUR_S": "600", "CHRYS_GARDE_TOUR_S": "90",
          "CHRYS_MOTEUR_PROCESSUS": "1"}  # CCM-186-A : moteur hors du processus (GIL) → débit 99 % de l'éteint  # délai dur par tour (CCM-164-A) ; + CHRYS_DOSSIER = <WORKING_DIR>/chrysalide_runs
VARIANTES = {
    "S1": {"env": COMMUN, "titre": "V0 : agent Franzen + CHRYS_MOTEUR + MoteurCle, repli immédiat, tutoriel éteint"},
    "S1b": {"env": COMMUN | {"CHRYS_BOUCLE": "1"}, "titre": "V1 : S1 + boucle à étages au blocage (CHRYS_BOUCLE)"},
    # CW-222 (D) : notebook final paramétrable. S0 = Franzen + notre cellule INERTE (aucun CHRYS_* : creer() → None, F-C2)
    "S0": {"env": {}, "titre": "S0 : agent Franzen seul (cellule Chrysalide inerte), 10 flux"},
    "F8": {"env": {}, "flux": 8, "titre": "F8 : agent Franzen seul, 8 flux (criblage CCM-210-A)"},
    "S1F8": {"env": COMMUN, "flux": 8, "titre": "S1 à 8 flux"},
    # CW-252/253 (D) : règle de prise de main MINIMALE. Le moteur ne joue que s'il a un plan vers un but (porte 2), court,
    # accepté par la garde de C (CHRYS_PARTIEL=2) ; sinon Franzen joue. Rien n'est injecté dans l'invite de Franzen.
    # Drapeaux = configuration du moteur seul qui gagne ses niveaux publics (CW-247 : 5 niveaux sur 20 jeux).
    "S2": {"env": COMMUN | {"CHRYS_PARTIEL": "2", "CHRYS_AMODAL": "1", "CHRYS_FORMES": "1", "CHRYS_COMPORTEMENT": "1",
                            "CHRYS_BUT_SUPPOSE": "1"},
           "titre": "S2 : S1 + prise de main minimale (plan vers un but, garde par aspect ; sinon Franzen)"},
    # CW-357 / CW-361 voie 2 (D) : Franzen CONSULTE le moteur. Même calcul que S2, mais le moteur ne joue jamais : son plan
    # devient une option versionnée que Franzen lit par inspect_options() / inspect_model() dans son outil Python
    # (patcher_inspect.py ; exige ARC3_PERSISTENT_FUNCTIONS=1 du v3, sinon CHRYS_INSPECT est retiré seul, Franzen inchangé)
    # CW-446 / CW-455 (D) : Franzen v3 PUR (aucune cellule Chrysalide, harnais non patché) + vérification du démarrage
    # (environnement, chargement, /health, PREMIÈRE INFÉRENCE, patience 2 h, durée de jeu réduite de l'attente)
    "R0": {"env": {}, "sans_cellule": True, "demarrage": True,
           "titre": "R0 : Franzen v3 pur + vérification du démarrage (attente robuste, journal)"},
    # Codex 28/10 (stratégie de score) : clone de R0 pour l'ablation « outils Python ». Franzen joue seul (cellule inerte
    # pour le moteur : aucun CHRYS_MOTEUR) ; nos outils de navigation (patcher_outils.py) entrent dans son REPL SEULEMENT
    # après CHRYS_OUTILS_APRES coups sans finir le niveau (stagnation), pour ne pas ralentir les niveaux qu'il résout vite.
    # Un échec du patch retire CHRYS_OUTILS seul (= R0). Témoin de l'ablation : R0.
    "RO": {"env": {"CHRYS_OUTILS": "1", "CHRYS_OUTILS_APRES": "40"}, "demarrage": True,
           "titre": "RO : R0 + outils de navigation dans le REPL de Franzen après 40 coups sans finir le niveau"},
    # Thomas 29/10 14 h 20 : soumission 31/10 = RO + faits épinglés (Codex, refs/codex/faits-films-29 823bbc2d). Franzen
    # joue seul ; outils comme RO ; en plus, sur un niveau qui traîne (CHRYS_FAITS_APRES coups dans la vie courante), un
    # bloc de COMPTES par action (image finale inchangée k/n, clics exclus, frontière RESET) est ajouté au message de tour :
    # faits seulement, ni conseil ni plan. Échec du patch → CHRYS_FAITS retiré seul (= RO). Témoin : RO.
    "ROF": {"env": {"CHRYS_OUTILS": "1", "CHRYS_OUTILS_APRES": "40", "CHRYS_FAITS": "1", "CHRYS_FAITS_APRES": "40"},
            "demarrage": True,
            "titre": "ROF : RO + faits épinglés (comptes par action, images finales) après 40 coups sans finir le niveau"},
    # Thomas 30/10 23 h 40 : soumission 1/11 = RO + porte v5 variante score, réglages de l'ABBA du 30/10 (manifeste dd5c3ef8,
    # abba_porte5.sh, ligne P5) sauf MAX_RUNTIME_MINUTES (le carnet fixe sa durée) et le chemin du paquet (embarqué, posé par la
    # cellule). Échec du contrôle du paquet → drapeaux de la porte retirés seuls (= RO). Témoin : RO. Essai : g50t et ka59 (la porte
    # joue), ft09 (non-régression).
    "ROP5": {"env": {"CHRYS_OUTILS": "1", "CHRYS_OUTILS_APRES": "40", "CHRYS_FAITS": "0", "CHRYS_FAITS_APRES": "40",
                     "CHRYS_GARDE_MUR_S": "1800", "CHRYS_HISTORIQUE_FIDELE": "1", "CHRYS_PORTE_V4": "0", "CHRYS_MONITEUR": "0",
                     "CHRYS_REFLEXES": "0", "CHRYS_ROUTEUR": "0", "CHRYS_VERIF": "0", "CHRYS_GRAPHE": "0", "CHRYS_BUDGET": "0",
                     "CHRYS_MOTEUR": "0", "CHRYS_PORTE5": "1", "CHRYS_STAGNATION_COUPS": "40", "CHRYS_PORTE5_ENFANTS": "10",
                     "CHRYS_PORTE5_BUDGET": "150", "CHRYS_PORTE5_REPET_MAX": "3", "CHRYS_PORTE5_ATTENTE_S": "90",
                     "CHRYS_PORTE5_MUR_S": "300", "CHRYS_PORTE5_STRICT": "0"},
             "demarrage": True, "paquet": "experiments/GEL27_moteur_seul_v2", "essai": ["g50t", "ka59", "ft09"],
             "titre": "ROP5 : RO + porte v5 variante score (moteur v4 isolé, sans LLM, au 1er tour et après 40 coups sans finir le niveau)"},
    "I": {"env": COMMUN | {"CHRYS_PARTIEL": "2", "CHRYS_AMODAL": "1", "CHRYS_FORMES": "1", "CHRYS_COMPORTEMENT": "1",
                           "CHRYS_BUT_SUPPOSE": "1", "CHRYS_INSPECT": "1"},
          "titre": "I : S2 calculé, jamais joué ; Franzen lit l'option du moteur (inspect_options / inspect_model)"},
}
ESSAI = ["ls20", "sk48", "ft09"]  # moteur attendu (ls20), jeu bloqué (sk48), jeu gagné par Franzen (ft09 : non-régression)
SCRIPTS = ("patcher_franzen.py", "patcher_garde.py", "patcher_inspect.py", "patcher_outils.py",
           "patcher_faits.py", "faits_franzen.py", "faits_bridge.py")
QWEN = tuple(sorted(str(p.relative_to(RACINE)) for p in (RACINE / "chrysalide/qwen").glob("*.py")))  # CW-362.2 : éteint


def fermeture(entrees=("garde", "branche", "logique.menu_mecanismes", "outils_repl", "porte_v5_enfant")):  # outils_repl : patcher_outils (RO)  # menu : impasse « règle » (H, C)
    """Modules chrysalide.arc3 atteints depuis les points d'entrée par TOUS les imports, y compris paresseux (dans les
    fonctions) : sur-ensemble sûr de ce que la chaîne charge (CW-181 / CCM-152-A : source Kaggle < 1 Mo)."""
    arc3, vus, pile = RACINE / "chrysalide/arc3", set(), list(entrees)
    while pile:
        m = pile.pop()
        f = next((p for p in (arc3 / f"{m.replace('.', '/')}.py", arc3 / m.replace(".", "/") / "__init__.py")
                  if p.is_file()), None)
        if f is None or f in vus:
            continue
        vus.add(f)
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("chrysalide.arc3"):
                base = n.module[len("chrysalide.arc3"):].lstrip(".")
                pile += [base] * bool(base) + [f"{base}.{a.name}".lstrip(".") for a in n.names]
            elif isinstance(n, ast.Import):
                pile += [a.name[len("chrysalide.arc3."):] for a in n.names if a.name.startswith("chrysalide.arc3.")]
    return sorted(vus)


def code(paquet=None):
    fichiers = {str(f.relative_to(RACINE)): f.read_text() for f in fermeture()}
    if paquet:  # fichiers suivis seulement, comme l'archive déployée au pod (ni .pyc ni reliquat)
        suivis = subprocess.run(["git", "ls-files", paquet], cwd=RACINE, capture_output=True, text=True, check=True).stdout.split()
        assert suivis, paquet
        fichiers |= {n: (RACINE / n).read_text() for n in suivis}
    fichiers |= {f"scripts/arc3/{n}": (RACINE / "scripts/arc3" / n).read_text() for n in SCRIPTS}
    fichiers |= {n: (RACINE / n).read_text() for n in QWEN}
    fichiers["chrysalide/__init__.py"] = ""
    fichiers["chrysalide/arc3/__init__.py"] = ""
    return fichiers


def cellule(nom, v, fichiers):
    brut = json.dumps(fichiers, sort_keys=True, ensure_ascii=False).encode()
    empreinte = hashlib.sha256(brut).hexdigest()
    b64 = base64.b64encode(lzma.compress(brut, preset=9 | lzma.PRESET_EXTREME)).decode()
    archive = "\n".join(repr(b64[i:i + 2000]) for i in range(0, len(b64), 2000))  # CW-181 : source Kaggle < 1 Mo
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RACINE, capture_output=True, text=True,
                            check=False).stdout.strip()
    sale = subprocess.run(["git", "status", "--porcelain", "--", "chrysalide/arc3", *QWEN, *(f"scripts/arc3/{n}" for n in SCRIPTS)],
                          cwd=RACINE, capture_output=True, text=True, check=False).stdout.strip()
    if sale:  # le notebook embarque l'arbre de travail : une version à soumettre se fabrique sur du code commité
        print("ATTENTION : code non commité embarqué :\n" + sale)
        commit += " + MODIFS NON COMMITÉES"
    return f'''# SPDX-License-Identifier: MIT-0
# CHRYSALIDE — variante {nom} : {v["titre"]}.
# Code : chrysalide/arc3 en JSON compressé xz + base64 (CW-181 : source < 1 Mo), base {commit}, SHA256 {empreinte[:16]}…\n# Source lisible : scripts/arc3/faire_notebook_S.py du dépôt Chrysalide. Patchs posés sur le harnais de Franzen.
# Repli : en SOUMISSION, tout échec de cette cellule éteint nos interrupteurs (Franzen pur) ; en ESSAI, il arrête tout.
import base64, glob, hashlib, json, lzma, os, subprocess, sys, sysconfig, traceback
from pathlib import Path
_CHRYS_ENV = {v["env"]!r}
_CHRYS_FLUX = {v.get("flux")!r}  # nombre de flux LLM simultanés (ARC3_MAX_ACTIVE_STREAMS) ; None = celui de Franzen (10)
if _CHRYS_FLUX is not None:  # hors du bloc de repli : vaut aussi en Franzen pur
    os.environ["ARC3_MAX_ACTIVE_STREAMS"] = str(_CHRYS_FLUX)
_CHRYS_ARCHIVE = (
{archive})
_CHRYS_SHA256 = {empreinte!r}
_CHRYS = WORKING_DIR / "chrysalide"
_ENTREES = globals().get("CHRYS_ENTREES", "/kaggle/input")  # surchargeable pour l'essai hors Kaggle
_harnais = Path(f"{{BUNDLE_DIR}}/src/ARC3-Inference")
_CHRYS_ETAPES = []
try:
    _brut = lzma.decompress(base64.b64decode(_CHRYS_ARCHIVE))
    if hashlib.sha256(_brut).hexdigest() != _CHRYS_SHA256:
        raise RuntimeError("archive Chrysalide corrompue (SHA256)")
    _CHRYS_FICHIERS = json.loads(_brut)
    _CHRYS_ETAPES.append(f"archive {{len(_CHRYS_FICHIERS)}} fichiers")
    for _nom, _texte in _CHRYS_FICHIERS.items():
        (_CHRYS / _nom).parent.mkdir(parents=True, exist_ok=True)
        (_CHRYS / _nom).write_text(_texte)
    for _p in ("patcher_franzen.py", "patcher_garde.py"):
        _r = subprocess.run([sys.executable, str(_CHRYS / "scripts/arc3" / _p), str(_harnais)], capture_output=True, text=True)
        if _r.returncode != 0 or _r.stdout.strip() not in ("patché", "déjà patché"):
            raise RuntimeError(f"{{_p}} NON appliqué : {{_r.stdout}} {{_r.stderr}}")
        _CHRYS_ETAPES.append(_p)
    if _CHRYS_ENV.get("CHRYS_INSPECT") == "1":  # voie 2 : un échec ici retire CHRYS_INSPECT seul (le reste tient)
        _r = subprocess.run([sys.executable, str(_CHRYS / "scripts/arc3/patcher_inspect.py"), str(_harnais)],
                            capture_output=True, text=True)
        if os.environ.get("ARC3_PERSISTENT_FUNCTIONS") != "1" or _r.returncode != 0 \
                or _r.stdout.strip() not in ("patché", "déjà patché"):
            _CHRYS_ENV = {{k: w for k, w in _CHRYS_ENV.items() if k != "CHRYS_INSPECT"}}
            _CHRYS_ETAPES.append(f"INSPECT RETIRÉ ({{os.environ.get('ARC3_PERSISTENT_FUNCTIONS')}}, {{_r.stdout.strip()[-200:]}} {{_r.stderr.strip()[-200:]}})")
        else:
            _CHRYS_ETAPES.append("patcher_inspect.py")
    if _CHRYS_ENV.get("CHRYS_OUTILS") == "1":  # outils V2' (RO) : un échec ici retire CHRYS_OUTILS seul (= R0)
        _r = subprocess.run([sys.executable, str(_CHRYS / "scripts/arc3/patcher_outils.py"), str(_harnais)],
                            capture_output=True, text=True)
        if os.environ.get("ARC3_PERSISTENT_FUNCTIONS") != "1" or _r.returncode != 0 \
                or _r.stdout.strip() not in ("patché", "déjà patché"):
            _CHRYS_ENV = {{k: w for k, w in _CHRYS_ENV.items() if not k.startswith("CHRYS_OUTILS")}}
            _CHRYS_ETAPES.append(f"OUTILS RETIRÉS ({{os.environ.get('ARC3_PERSISTENT_FUNCTIONS')}}, {{_r.stdout.strip()[-200:]}} {{_r.stderr.strip()[-200:]}})")
        else:
            _CHRYS_ETAPES.append("patcher_outils.py")
    if _CHRYS_ENV.get("CHRYS_FAITS") in ("0", "1"):  # patch posé même éteint si le drapeau est explicite (ROP5 = harnais de l'ABBA) ; faits épinglés (ROF), APRÈS les outils : un échec retire CHRYS_FAITS seul (= RO)
        _r = subprocess.run([sys.executable, str(_CHRYS / "scripts/arc3/patcher_faits.py"), str(_harnais)],
                            capture_output=True, text=True)
        if _r.returncode != 0 or _r.stdout.strip() not in ("patché", "déjà patché"):
            _CHRYS_ENV = {{k: w for k, w in _CHRYS_ENV.items() if not k.startswith("CHRYS_FAITS")}}
            _CHRYS_ETAPES.append(f"FAITS RETIRÉS ({{_r.stdout.strip()[-200:]}} {{_r.stderr.strip()[-200:]}})")
        else:
            _CHRYS_ETAPES.append("patcher_faits.py")
    _tag = f"cp{{sys.version_info.major}}{{sys.version_info.minor}}"
    _roues = sorted(glob.glob(f"{{_ENTREES}}/**/clingo-*-{{_tag}}-*.whl", recursive=True))
    try:
        import clingo  # noqa: F401  (déjà présent dans l'image ?)
    except ImportError:
        if not _roues:
            raise RuntimeError(f"aucune roue clingo {{_tag}} sous /kaggle/input (dataset chrysalide-roues attaché ?)")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--no-index", "--no-deps",
                               "--disable-pip-version-check", _roues[-1]], stdout=subprocess.DEVNULL)
    import clingo
    _c = clingo.Control(["0"]); _c.add("base", [], "a. b :- a."); _c.ground([("base", [])])
    _m = []; _c.solve(on_model=lambda m: _m.append(str(m)))
    assert _m and sorted(_m[0].split()) == ["a", "b"], _m
    _CHRYS_ETAPES.append(f"clingo {{clingo.__version__}}")
    if str(_harnais) not in sys.path:
        sys.path.insert(0, str(_harnais))
    if str(_CHRYS) not in sys.path:  # chrysalide.qwen (demander_qwen), importé tel quel par le moteur
        sys.path.insert(0, str(_CHRYS))
    import importlib
    for _mod in ("garde", "branche", "moteur", "logique.moteur_cle"):
        importlib.import_module(f"inference.chrysalide_arc3.{{_mod}}")
    from inference.chrysalide_arc3.logique.moteur_cle import MoteurCle
    MoteurCle()
    assert "CHRYSALIDE-GARDE" in (_harnais / "inference/framework/solver.py").read_text()
    _CHRYS_ETAPES.append("imports + MoteurCle")
    _CHRYS_PAQUET = {v.get("paquet")!r}
    if _CHRYS_ENV.get("CHRYS_PORTE5") == "1":  # l'enfant tourne en python -I, sans le chemin du carnet : on charge ici ce qu'il chargera
        _paq = _CHRYS / _CHRYS_PAQUET
        _chemins = [str(_paq), str(_paq / "livraison_p1/code"), str(_paq / "references/astra4/livraison_astra4/ajouts")]
        _r = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path[:0] = " + repr(_chemins) + "; import chrysalide.arc3.logique, agent_p1.jouer, agent_p1.labo, agent_p1.journal, boucle_v4.fantome_general, boucle_v4.poussee_generale"],
                            capture_output=True, text=True, cwd=str(WORKING_DIR), timeout=120)
        if _r.returncode:
            _CHRYS_ENV = {{k: w for k, w in _CHRYS_ENV.items() if not k.startswith(("CHRYS_PORTE5", "CHRYS_STAGNATION"))}}
            _CHRYS_ETAPES.append(f"PORTE5 RETIRÉE (= RO) ({{_r.stderr.strip()[-300:]}})")
        else:
            _CHRYS_ENV = _CHRYS_ENV | {{"CHRYS_PORTE_V4_PAQUET": str(_paq)}}
            _CHRYS_ETAPES.append("paquet porte v5")
    os.environ.update(_CHRYS_ENV | {{"CHRYS_DOSSIER": str(WORKING_DIR / "chrysalide_runs")}})
    # CW-362.2 : serveur de Franzen pour demander_qwen (n'allume rien : seuls les drapeaux d'impasse posent des questions)
    if "SERVER_BASE_URL" in globals() and _CHRYS_ENV:
        os.environ.update({{"CHRYS_QWEN_SERVEUR": "sglang", "CHRYS_QWEN_URL": str(SERVER_BASE_URL),
                           "CHRYS_QWEN_MODELE": str(globals().get("SERVED_MODEL_NAME", ""))}})
    (WORKING_DIR / "chrysalide_runs").mkdir(parents=True, exist_ok=True)
    print("CHRYSALIDE {nom} : prêt", _CHRYS_ETAPES, {{k: w for k, w in os.environ.items() if k.startswith("CHRYS_")}})
    if not TRUE_SUBMISSION:  # CW-174 : cœurs et charge RÉELS de la machine Kaggle, toutes les 2 min (essai seulement)
        import json as _json, resource as _res, threading as _th, time as _t
        def _lire(p):
            try:
                return Path(p).read_text().strip()
            except OSError:
                return None
        def _cpu():
            with open(WORKING_DIR / "chrysalide_cpu.jsonl", "a") as f:
                f.write(_json.dumps({{"nproc": os.cpu_count(), "affinite": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                                     "cpu_max": _lire("/sys/fs/cgroup/cpu.max"), "py": sys.version}}) + "\\n")
                while True:
                    r = _res.getrusage(_res.RUSAGE_SELF)
                    f.write(_json.dumps({{"t": _t.time(), "charge": os.getloadavg(), "proc_cpu_s": r.ru_utime + r.ru_stime,
                                         "fils_cpu_s": sum(getattr(_res.getrusage(_res.RUSAGE_CHILDREN), k)
                                                           for k in ("ru_utime", "ru_stime")),
                                         "threads": _th.active_count(), "cgroup": _lire("/sys/fs/cgroup/cpu.stat")}}) + "\\n")
                    f.flush()
                    _t.sleep(120)
        _th.Thread(target=_cpu, daemon=True, name="chrysalide_cpu").start()
except Exception:
    _trace = traceback.format_exc()
    for _k in list(os.environ):
        if _k.startswith("CHRYS_"):
            del os.environ[_k]
    if not TRUE_SUBMISSION:
        raise
    (WORKING_DIR / "CHRYSALIDE_REPLI.txt").write_text(f"étapes réussies {{_CHRYS_ETAPES}}\\n{{_trace}}")
    print("CHRYSALIDE {nom} : ÉCHEC → interrupteurs éteints, FRANZEN PUR", _CHRYS_ETAPES, _trace)
'''


def main(nom="S1", dossier=None, *reglages):
    """reglages : « flux=N » et « CHRYS_X=valeur » (surcharge de la variante ; le nom de sortie les porte)."""
    v = dict(VARIANTES[nom])
    v["env"] = dict(v["env"])
    suffixe = ""
    for r in reglages:
        k, val = r.split("=", 1)
        if k == "flux":
            v["flux"] = int(val)
        else:
            v["env"][k] = val
        suffixe += f"_{k.removeprefix('CHRYS_').lower()}{val}"
    if suffixe:
        v["titre"] += f" ; réglages {' '.join(reglages)}"
    sortie = Path(dossier or RACINE / "kaggle") / f"notebook_{nom}{suffixe}.ipynb"
    nb = json.loads(SOURCE.read_text())
    cellules = nb["cells"]
    i10 = next(i for i, c in enumerate(cellules) if "taaf_kaggle_sources.pth" in "".join(c["source"]))
    i16 = next(i for i, c in enumerate(cellules) if "demo_excluded_games = []" in "".join(c["source"]))
    publics = [x.strip().split("-")[0] for x in (RACINE / "experiments/arc3/jeux_publics.txt").read_text().split() if x.strip()]
    essai = v.get("essai", ESSAI)
    exclus = sorted(set(publics) - set(essai))
    assert len(publics) == 25 and len(exclus) == 22, (len(publics), len(exclus))
    s16 = "".join(cellules[i16]["source"])
    s16 = s16.replace("demo_excluded_games = [] if TRUE_SUBMISSION else []",
                      f"demo_excluded_games = [] if TRUE_SUBMISSION else {exclus!r}  # CHRYSALIDE : essai sur {essai}", 1)
    ajout = ("\nif not TRUE_SUBMISSION:  # CHRYSALIDE : essai = 1 passe, 48 min par jeu (≈ temps de flux par jeu en soumission)\n"
             "    bm.n_passes = 1\n"
             "    bm.solver.concurrency = (25 - len(demo_excluded_games)) * bm.n_passes\n"
             "    bm.solver.max_runtime_s_per_game = 532*60*10 // 110\n")
    s16 = s16.replace("\n# show config", ajout + "\n# show config", 1)
    assert "CHRYSALIDE : essai sur" in s16 and "532*60*10 // 110" in s16
    cellules[i16]["source"] = s16.splitlines(keepends=True)
    fichiers = code(v.get("paquet"))
    if v.get("demarrage"):  # avant « Starting benchmark » (après la cellule 16 de Franzen), et une ligne de fin après
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from demarrage_kaggle import APRES, AVANT
        i20 = next(i for i, c in enumerate(cellules) if "print('Starting benchmark...')" in "".join(c["source"]))
        for j, src in ((i20 + 1, APRES), (i20, AVANT)):
            cellules.insert(j, {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                                "source": src.splitlines(keepends=True)})
    if not v.get("sans_cellule"):
        cellules.insert(i10 + 1, {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                                  "source": cellule(nom, v, fichiers).splitlines(keepends=True)})
    titre = copy.deepcopy(cellules[0])
    titre["source"] = [(f"### CHRYSALIDE — variante {nom} (soumettable)\n{v['titre']}. Copie du notebook Franzen v3 + une "
                       f"cellule après « Import the bundled source » (notre code en clair, MIT-0). "
                       f"Entrées : celles du v3 + le dataset chrysalide-roues (roue clingo). Essai interactif : "
                       f"{', '.join(essai)}, 1 passe, 48 min par jeu.\n")]
    cellules.insert(0, titre)
    for c in cellules:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    sortie.write_text(json.dumps(nb, ensure_ascii=False))  # compact : source Kaggle < 1 Mo (CW-181)
    print(f"{sortie} : {len(cellules)} cellules ; cellule Chrysalide en {i10 + 2} ; "
          f"{len(fichiers)} fichiers ; {sortie.stat().st_size // 1024} Ko ; essai {essai}")


if __name__ == "__main__":
    a = sys.argv[1:] or ["S1"]
    main(a[0], None, *a[1:])
