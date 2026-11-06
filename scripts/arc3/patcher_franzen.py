# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""Pose l'architecture Chrysalide dans une COPIE du harnais de Franzen (jamais dans tiers/ lui-même).

usage : python scripts/arc3/patcher_franzen.py <dossier ARC3-Inference copié>
- copie chrysalide/arc3/{archi,branche,graphe,duck}.py (et le moteur formel de CHRYS_MOTEUR, voir FICHIERS) dans
  <dossier>/inference/chrysalide_arc3/ ;
- insère dans inference/framework/solver.py, au début de chaque tour de boucle, juste avant l'appel au modèle :
      if not hasattr(self, "_chrys"): self._chrys = creer(self)
      if self._chrys is not None and self._chrys.tour(): continue
- idempotent ; échoue si l'ancre n'est pas trouvée exactement une fois (version de Franzen différente).
Interrupteurs CHRYS_* tous éteints = harnais de Franzen inchangé (creer() renvoie None)."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUE = "# CHRYSALIDE"
# Tout chrysalide/arc3 (et logique/) : CHRYS_MOTEUR / CHRYS_MOTEUR_CLE tirent de plus en plus de modules (ressource,
# correspond, temps, abstraction…) ; ils ne sont chargés que si un drapeau est allumé (imports paresseux dans branche.py).
FICHIERS = tuple(sorted(str(f.relative_to(RACINE / "chrysalide/arc3")) for f in (RACINE / "chrysalide/arc3").rglob("*.py")
                        if "__pycache__" not in f.parts))
ANCRE = "                if retry_analysis_step is None:\n                    self.analysis_step += 1\n"
AJOUT = (f"                {MARQUE} : routeur sans modèle (interrupteurs CHRYS_*, éteints = Franzen inchangé)\n"
         "                if not hasattr(self, \"_chrys\"):\n"
         "                    from inference.chrysalide_arc3.branche import creer as _chrys_creer\n"
         "                    self._chrys = _chrys_creer(self)\n"
         "                if self._chrys is not None and retry_analysis_step is None and self._chrys.tour():\n"
         "                    continue\n")


def patcher(dossier):
    dossier = Path(dossier)
    paquet = dossier / "inference" / "chrysalide_arc3"
    paquet.mkdir(exist_ok=True)
    (paquet / "__init__.py").write_text("")
    for nom in FICHIERS:
        t = (RACINE / "chrysalide/arc3" / nom).read_text()
        (paquet / nom).parent.mkdir(exist_ok=True)
        (paquet / nom).write_text(t.replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.")
                                  .replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import"))
    solveur = dossier / "inference" / "framework" / "solver.py"
    s = solveur.read_text()
    if MARQUE in s:
        return "déjà patché"
    if s.count(ANCRE) != 1:
        raise SystemExit(f"ancre trouvée {s.count(ANCRE)} fois dans {solveur} : version de Franzen inattendue")
    solveur.write_text(s.replace(ANCRE, AJOUT + ANCRE))
    return "patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
