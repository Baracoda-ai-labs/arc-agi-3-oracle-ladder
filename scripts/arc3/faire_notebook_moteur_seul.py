# SPDX-License-Identifier: MIT-0
"""D (CW-431) : fabrique le carnet Kaggle « moteur seul » (CPU, hors ligne, sans LLM) → kaggle/notebook_moteur_seul.ipynb.
Embarque, en JSON compressé xz + base64 (SHA256 vérifié) :
- les 59 fichiers du paquet figé de C (`experiments/GEL27_moteur_seul`, listés par SHA256SUMS) + SHA256SUMS + EMPREINTE.txt ;
  la cellule refait la vérification de `verifier.sh` (chaque fichier, puis l'empreinte globale) AVANT de jouer ;
- l'adaptateur Kaggle de C (`experiments/kaggle_moteur_seul/adaptateur/chrysalide/…`), importé AVANT `agent_p1.jouer`
  (piège d'import, CCM-314-C) ;
- le pilote de D (`experiments/kaggle_moteur_seul/pilote.py`) : garde absolue des 5 témoins, feuille de score unique.
Vraie soumission (KAGGLE_IS_COMPETITION_RERUN) : passerelle Kaggle, Arcade COMPETITION. Essai (Save & Run) : fichiers
d'environnement de la compétition, hors ligne, témoins exclus, submission.parquet factice comme le carnet de Franzen.
Usage : uv run python scripts/arc3/faire_notebook_moteur_seul.py [dossier de sortie] [v1|v2]  (v2 = paquet avec films F1)"""
import base64
import hashlib
import json
import lzma
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PAQUETS = {"v1": RACINE / "experiments/GEL27_moteur_seul",      # 81126387, empreinte a6f847da…
           "v2": RACINE / "experiments/GEL27_moteur_seul_v2",   # films F1 + nouveauté de G (CCM-325-C)
           "v3": RACINE / "experiments/GEL27_moteur_seul_v3"}   # v2 + T1 (MoteurC dans P1, clingo), CCM-335-C


def env_du_paquet(version):
    """Drapeaux que `lancer.sh` du paquet pose lui-même (`export CHRYS_X=val`) : le carnet appelle jouer_jeu sans lui
    (CCM-322-C / CCM-325-C) et doit les reproduire à l'identique."""
    import re
    texte = (PAQUETS[version] / "lancer.sh").read_text()
    out = {}
    for ligne in re.findall(r"^export (.+)$", texte, flags=re.MULTILINE):  # v3 : plusieurs drapeaux par ligne
        out.update(re.findall(r"(CHRYS_[A-Z0-9_]+)=(\S+)", ligne))
    return out


PAQUET = PAQUETS["v1"]
KMS = RACINE / "experiments/kaggle_moteur_seul"
DELAI_JEU_S = 20 * 60  # aucun jeu au-delà de 20 min (110 jeux en 9 h ≈ 4,9 min en moyenne ; pire cas P1 : 3 000 coups)


def fichiers(version="v1"):
    PAQUET = PAQUETS[version]
    f = {}
    for ligne in (PAQUET / "SHA256SUMS").read_text().splitlines():
        _, chemin = ligne.split(None, 1)
        chemin = chemin.removeprefix("./")
        f[f"paquet/{chemin}"] = (PAQUET / chemin).read_text()
    for n in ("SHA256SUMS", "EMPREINTE.txt"):
        f[f"paquet/{n}"] = (PAQUET / n).read_text()
    for p in sorted((KMS / "adaptateur/chrysalide").rglob("*.py")):
        f[f"adaptateur/{p.relative_to(KMS / 'adaptateur')}"] = p.read_text()
    f["pilote.py"] = (KMS / "pilote.py").read_text()
    return f


CELLULE = r'''# SPDX-License-Identifier: MIT-0
# CHRYSALIDE — moteur seul (paquet GEL27 de C, empreinte {global_}), sans LLM, CPU. Source lisible :
# scripts/arc3/faire_notebook_moteur_seul.py du dépôt Chrysalide. Archive SHA256 {sha16}…
import base64, hashlib, json, lzma, os, subprocess, sys, time
from pathlib import Path
T0 = time.time()
TRUE_SUBMISSION = os.environ.get("KAGGLE_IS_COMPETITION_RERUN", "").strip().lower() in {{"1", "true"}}
WORKING_DIR = Path("/kaggle/working")
ROUES = "/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels"
os.environ.update({env!r})  # paquet {version} : ce que son lancer.sh pose lui-même
print(f"moteur seul {version} : TRUE_SUBMISSION={{TRUE_SUBMISSION}}")

# 1. Code : archive vérifiée, puis paquet figé vérifié fichier par fichier (comme verifier.sh)
_ARCHIVE = (
{archive})
_brut = lzma.decompress(base64.b64decode(_ARCHIVE))
assert hashlib.sha256(_brut).hexdigest() == "{sha}", "archive corrompue"
ICI = WORKING_DIR / "chrysalide_moteur"
for nom, texte in json.loads(_brut).items():
    (ICI / nom).parent.mkdir(parents=True, exist_ok=True)
    (ICI / nom).write_text(texte)
for ligne in (ICI / "paquet/SHA256SUMS").read_text().splitlines():
    h, chemin = ligne.split(None, 1)
    assert hashlib.sha256((ICI / "paquet" / chemin.removeprefix("./")).read_bytes()).hexdigest() == h, f"modifié : {{chemin}}"
_g = hashlib.sha256((ICI / "paquet/SHA256SUMS").read_bytes()).hexdigest()
assert f"global {{_g}}" in (ICI / "paquet/EMPREINTE.txt").read_text(), "empreinte globale"
print("paquet conforme : global", _g, "; adaptateur", hashlib.sha256((ICI / "adaptateur/chrysalide/arc3/logique/jeux.py").read_bytes()).hexdigest()[:16])

# 2. arc-agi depuis les roues de la compétition (hors ligne), comme le carnet de Franzen
subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--no-index", "--no-warn-conflicts",
                       "--disable-pip-version-check", "--find-links", ROUES, "arc-agi"], stdout=subprocess.DEVNULL)

{roues}
{imports}
# 4. Arcade : passerelle en soumission, fichiers de la compétition en essai
import arc_agi  # noqa: E402
from urllib.request import urlopen  # noqa: E402
if TRUE_SUBMISSION:
    base = os.environ.setdefault("ARC_BASE_URL", "http://gateway:8001/")
    os.environ.setdefault("ARC_API_KEY", "test-key-123")
    fin = time.monotonic() + 600
    while True:
        try:
            with urlopen(f"{{base}}api/games", timeout=10) as r:
                if r.status < 500:
                    break
        except Exception as e:  # noqa: BLE001
            if time.monotonic() > fin:
                raise RuntimeError(f"passerelle absente : {{e!r}}")
        time.sleep(5)
    arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.COMPETITION, arc_base_url=base, environments_dir="")
else:
    env_dir = str(Path(ROUES).parent / "environment_files")
    arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=env_dir)

# 5. Mémoire inter-jeux inscriptible, puis la partie (garde témoins dans le pilote ET dans l'adaptateur)
SORTIE = WORKING_DIR / "moteur_seul"
MEMOIRE = SORTIE / "memoire_inter_jeux"
MEMOIRE.mkdir(parents=True, exist_ok=True)
for f in (ICI / "paquet/livraison_p1/memoire_depart").glob("*.json"):
    if not (MEMOIRE / f.name).exists():
        (MEMOIRE / f.name).write_text(f.read_text())


def jouer(gid):
    res = J.jouer_jeu("", gid, str(SORTIE), 150, str(MEMOIRE), graine=0)
    return {{"niveaux": sum(bool(x.get("victoire")) for x in res), "coups": [x.get("coups") for x in res]}}


resultats = pilote.lancer(arcade, jouer, SORTIE, T0, configurer=jeux.configurer, delai_jeu_s={delai})
print("jeux joués", sum("erreur" not in r and "saute" not in r for r in resultats), "/", len(resultats),
      "; niveaux", sum(r.get("niveaux", 0) for r in resultats), "; erreurs", sum("erreur" in r for r in resultats),
      f"; {{(time.time() - T0) / 60:.1f}} min")
if not TRUE_SUBMISSION:  # un essai n'est pas noté, mais Kaggle attend un submission.parquet (comme le carnet de Franzen)
    import pandas as pd
    pd.DataFrame([["1_0", "1", True, 1]], columns=["row_id", "game_id", "end_of_game", "score"]).to_parquet(
        WORKING_DIR / "submission.parquet", index=False)
'''


IMPORTS_REDUIT = r'''# 3. Imports : l'adaptateur AVANT agent_p1.jouer (piège d'import, CCM-314-C) ; racine du paquet HORS du chemin
sys.path[:0] = [str(ICI / "adaptateur"), str(ICI / "paquet/livraison_p1/code"),
                str(ICI / "paquet/references/astra4/livraison_astra4/ajouts"), str(ICI)]
import chrysalide.arc3.logique.jeux as jeux  # noqa: E402
import agent_p1.jouer as J  # noqa: E402
import pilote  # noqa: E402
assert hasattr(jeux, "configurer") and "adaptateur" in jeux.__file__, jeux.__file__
'''

IMPORTS_PLEIN = r'''# 3. Imports (paquet PLEIN, v3, CCM-335-C) : le `chrysalide` COMPLET du paquet (MoteurC) ; SEUL son module `jeux` est
# remplacé par l'adaptateur, toujours AVANT agent_p1.jouer (un `chrysalide` réduit devant cacherait MoteurC : T1 muet)
import importlib.util  # noqa: E402
sys.path[:0] = [str(ICI / "paquet"), str(ICI / "paquet/livraison_p1/code"),
                str(ICI / "paquet/references/astra4/livraison_astra4/ajouts"), str(ICI)]
import chrysalide.arc3.logique as _logique  # noqa: E402
_spec = importlib.util.spec_from_file_location("chrysalide.arc3.logique.jeux", ICI / "adaptateur/chrysalide/arc3/logique/jeux.py")
jeux = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = jeux
_spec.loader.exec_module(jeux)
_logique.jeux = jeux
import agent_p1.jouer as J  # noqa: E402
import pilote  # noqa: E402
import chrysalide.arc3.moteur as _moteur  # noqa: E402
assert hasattr(jeux, "configurer") and "adaptateur" in jeux.__file__, jeux.__file__
assert "paquet" in _moteur.__file__, _moteur.__file__
print("MoteurC chargé depuis", _moteur.__file__)
'''

ROUES_CLINGO = r'''# 2 b. clingo et cffi (MoteurC) : jeu de données « chrysalide-roues » attaché, installation hors ligne
import glob as _glob  # noqa: E402
_tag = f"cp{{sys.version_info.major}}{{sys.version_info.minor}}"
for _p in ("cffi", "clingo"):
    try:
        __import__(_p)
    except ImportError:
        _w = sorted(_glob.glob(f"/kaggle/input/**/{{_p}}-*-{{_tag}}-*.whl", recursive=True))
        if not _w:
            raise RuntimeError(f"roue {{_p}} {{_tag}} absente : attacher le jeu de données chrysalide-roues")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--no-index", "--no-deps",
                               "--disable-pip-version-check", _w[-1]], stdout=subprocess.DEVNULL)
import clingo  # noqa: E402
print("clingo", clingo.__version__)
'''


def carnet(version="v1"):
    PAQUET = PAQUETS[version]
    f = fichiers(version)
    brut = json.dumps(f, sort_keys=True, ensure_ascii=False).encode()
    sha = hashlib.sha256(brut).hexdigest()
    b64 = base64.b64encode(lzma.compress(brut, preset=9 | lzma.PRESET_EXTREME)).decode()
    archive = "\n".join(repr(b64[i:i + 2000]) for i in range(0, len(b64), 2000))
    glob_ = next(x.split()[1] for x in (PAQUET / "EMPREINTE.txt").read_text().splitlines() if x.startswith("global "))
    plein = (PAQUET / "chrysalide/arc3/moteur.py").exists()
    code = CELLULE.format(archive=archive, sha=sha, sha16=sha[:16], global_=glob_[:16], delai=DELAI_JEU_S,
                          env=env_du_paquet(version), version=version,
                          roues=ROUES_CLINGO.format() if plein else "",
                          imports=IMPORTS_PLEIN if plein else IMPORTS_REDUIT)
    titre = ("### CHRYSALIDE — moteur seul (sans LLM, CPU)\nPaquet figé GEL27 (agent P1 + inventeur, exploration générique), "
             "joué jeu par jeu à travers l'API d'évaluation. Aucun modèle de langage. Les 5 jeux témoins (vc33, tu93, "
             "wa30, s5i5, cn04) ne sont jamais joués. Code ouvert : MIT-0.\n")
    nb = {"cells": [{"cell_type": "markdown", "metadata": {}, "source": titre.splitlines(keepends=True)},
                    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                     "source": code.splitlines(keepends=True)}],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    return nb, code, len(f)


def main(dossier=None, version="v1"):
    nb, _code, n = carnet(version)
    sortie = Path(dossier or RACINE / "kaggle") / f"notebook_moteur_seul{'' if version == 'v1' else '_' + version}.ipynb"
    sortie.write_text(json.dumps(nb, ensure_ascii=False))
    print(f"{sortie} : {n} fichiers ; {sortie.stat().st_size // 1024} Ko")
    return sortie


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a not in PAQUETS]
    main(args[0] if args else None, next((a for a in sys.argv[1:] if a in PAQUETS), "v1"))
