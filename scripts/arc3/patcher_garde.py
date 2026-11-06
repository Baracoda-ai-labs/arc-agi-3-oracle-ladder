# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""Soumission (D, CW-161) : à appliquer APRÈS patcher_franzen.py. Remplace, dans le bloc CHRYSALIDE de solver.py,
`branche.creer` par `garde.creer` (repli Franzen pur sur toute exception, plafond de temps par jeu : chrysalide/arc3/garde.py).
usage : python scripts/arc3/patcher_garde.py <dossier ARC3-Inference copié>   ; idempotent ; échoue si l'ancre manque."""
import sys
from pathlib import Path

AVANT = "from inference.chrysalide_arc3.branche import creer as _chrys_creer"
APRES = "from inference.chrysalide_arc3.garde import creer as _chrys_creer  # CHRYSALIDE-GARDE"


def patcher(dossier):
    solveur = Path(dossier) / "inference" / "framework" / "solver.py"
    s = solveur.read_text()
    if "CHRYSALIDE-GARDE" in s:
        return "déjà patché"
    if s.count(AVANT) != 1:
        raise SystemExit(f"ancre trouvée {s.count(AVANT)} fois dans {solveur} : patcher_franzen.py d'abord")
    if not (Path(dossier) / "inference" / "chrysalide_arc3" / "garde.py").is_file():
        raise SystemExit("garde.py absent du paquet chrysalide_arc3 : patcher_franzen.py d'abord")
    solveur.write_text(s.replace(AVANT, APRES))
    return "patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
