# SPDX-License-Identifier: MIT-0
"""CW-064 : fabrique kaggle/notebook_C.ipynb (bloc C sur Kaggle, MODE ESSAI) à partir du notebook Franzen v3 de Thomas.
- une cellule ajoutée juste après la cellule 4 (application du patch de Franzen) : écrit en clair consignes.py et
  patcher_consignes.py (B, MIT-0), applique le patch au harnais, échoue AUSSITÔT si l'ancre manque ou si
  l'on est en vraie soumission, et pose CHRYS_EPINGLE=1, CHRYS_AUDIT=1, CHRYS_LIBELLES=1 ;
- cellule 16 (réglages) : 3 passes, et les 15 jeux publics hors criblage exclus (demo_excluded_games) ;
- sorties effacées ; aucune clé, aucun jeu de données à téléverser.
Variante C' (CW-070, amendement C' de B) : `... faire_notebook_C.py prime` → kaggle/notebook_Cprime.ipynb ; ajoute le patch
outils (A : chrys_* + chrys_verifier) et CHRYS_AUDIT_PREDIRE=1, CHRYS_OUTILS=1, CHRYS_VERIFIER=1.
Usage : uv run python scripts/arc3/faire_notebook_C.py [prime]   (amendement C + addendum 1 de B ; criblage de CCM-045-B)"""
import copy
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "tiers/franzen_notebook/arc-agi-3-milestone-2-solution_v3.ipynb"
VARIANTES = {
    "C": {"sortie": "kaggle/notebook_C.ipynb", "env": {"CHRYS_EPINGLE": "1", "CHRYS_AUDIT": "1", "CHRYS_LIBELLES": "1"},
          "patchs": [("consignes", "CHRYSALIDE-CONSIGNES")]},
    "Cprime": {"sortie": "kaggle/notebook_Cprime.ipynb",
               "env": {"CHRYS_EPINGLE": "1", "CHRYS_AUDIT": "1", "CHRYS_LIBELLES": "1", "CHRYS_AUDIT_PREDIRE": "1",
                       "CHRYS_OUTILS": "1", "CHRYS_VERIFIER": "1"},
               "patchs": [("consignes", "CHRYSALIDE-CONSIGNES"), ("outils", "CHRYSALIDE-OUTILS")]},
}
MODULES = {"consignes": "consignes.py", "outils": "outils_repl.py"}
CRIBLAGE = ["bp35", "lf52", "ka59", "ls20", "re86", "sp80", "dc22", "sc25", "tr87", "m0r0"]
PASSES = 3


def cellule_chrysalide(nom, v):
    ecrits = []
    for patch, _ in v["patchs"]:
        mod, pat = MODULES[patch], f"patcher_{patch}.py"
        ecrits.append(f'(_CHRYS / "chrysalide/arc3/{mod}").write_text({(RACINE / "chrysalide/arc3" / mod).read_text()!r})')
        ecrits.append(f'(_CHRYS / "scripts/arc3/{pat}").write_text({(RACINE / "scripts/arc3" / pat).read_text()!r})')
    appliques = "\n".join(
        f'_appliquer("patcher_{p}.py", "# {m}")' for p, m in v["patchs"])
    return f'''# SPDX-License-Identifier: MIT-0
# CHRYSALIDE — bloc {nom}, MODE ESSAI (CW-064/070 ; amendements C, C' et addendum 1 de C, session B).
# Écrit nos fichiers en clair, applique nos patchs au harnais déjà patché par Franzen, échoue tout de suite sinon.
import os, subprocess, sys
from pathlib import Path
assert not TRUE_SUBMISSION, "notebook {nom} = essai sur les jeux publics : ne pas le soumettre"
_CHRYS = Path("/kaggle/working/chrysalide")
(_CHRYS / "chrysalide/arc3").mkdir(parents=True, exist_ok=True)
(_CHRYS / "scripts/arc3").mkdir(parents=True, exist_ok=True)
{chr(10).join(ecrits)}
_harnais = Path(f"{{BUNDLE_DIR}}/src/ARC3-Inference")
def _appliquer(patcher, marque):
    r = subprocess.run([sys.executable, str(_CHRYS / "scripts/arc3" / patcher), str(_harnais)], capture_output=True, text=True)
    print(patcher, r.stdout, r.stderr)
    if r.returncode != 0 or r.stdout.strip() not in ("patché", "déjà patché"):
        raise RuntimeError(f"CHRYSALIDE : {{patcher}} NON appliqué (ancre absente ?) — arrêt pour ne pas gaspiller le quota")
    assert marque in (_harnais / "inference/agent/tool_agent.py").read_text(), marque
{appliques}
os.environ.update({v["env"]!r})
print("CHRYSALIDE : bloc {nom} posé, interrupteurs", {{k: w for k, w in os.environ.items() if k.startswith("CHRYS_")}})
'''


def main(nom="C"):
    v = VARIANTES[nom]
    SORTIE = RACINE / v["sortie"]
    nb = json.loads(SOURCE.read_text())
    cellules = nb["cells"]
    i4 = next(i for i, c in enumerate(cellules) if c["cell_type"] == "code"
              and 'subprocess.run(["git", "apply"' in "".join(c["source"]))  # la cellule qui APPLIQUE le patch de Franzen
    i16 = next(i for i, c in enumerate(cellules) if "demo_excluded_games = []" in "".join(c["source"]))
    publics = [ligne.strip().split("-")[0] for ligne in (RACINE / "experiments/arc3/jeux_publics.txt").read_text().split()
               if ligne.strip()]
    exclus = sorted(set(publics) - set(CRIBLAGE))
    assert len(exclus) == 15 and set(CRIBLAGE) <= set(publics), (len(exclus), CRIBLAGE)
    s16 = "".join(cellules[i16]["source"])
    s16 = s16.replace("bm.n_passes = 4\n", f"bm.n_passes = {PASSES}  # CHRYSALIDE bloc C : 3 passes = 3 graines\n", 1)
    s16 = s16.replace("demo_excluded_games = [] if TRUE_SUBMISSION else []",
                      f"demo_excluded_games = [] if TRUE_SUBMISSION else {exclus!r}  # CHRYSALIDE : criblage de 10 jeux", 1)
    assert f"bm.n_passes = {PASSES}" in s16 and "CHRYSALIDE : criblage" in s16
    cellules[i16]["source"] = s16.splitlines(keepends=True)
    nouvelle = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                "source": cellule_chrysalide(nom, v).splitlines(keepends=True)}
    cellules.insert(i4 + 1, nouvelle)
    titre = copy.deepcopy(cellules[0])
    titre["source"] = [(f"### CHRYSALIDE — bloc {nom} (essai, non soumis)\nCopie du notebook Franzen v3 + une cellule (après la "
                       f"cellule 4) : consignes d'épinglage, d'audit et de libellés (MIT-0). Criblage de "
                       f"10 jeux publics : {', '.join(CRIBLAGE)} ; {PASSES} passes.\n")]
    cellules.insert(0, titre)
    for c in cellules:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print(f"{SORTIE} : {len(cellules)} cellules ; cellule Chrysalide en {i4 + 2} ; exclus {exclus}")


if __name__ == "__main__":
    main("Cprime" if sys.argv[1:] == ["prime"] else "C")
