# SPDX-License-Identifier: MIT-0
"""F (CW-445, « même budget partout ») : bras C de diag4 (règles et perception exactes = vrai jeu comme simulateur,
but INFÉRÉ) relancé avec le budget de temps de D (600 s au lieu de 120 s ; nœuds réels 3 000 → 1 000 000), sur les
niveaux où D gagne et où C manquait de budget. Même amorce (40 coups, graine 0), même induction (limite 120 s).
Usage : uv run python experiments/oracle/bras_C_600.py <k> <jeu,jeu…> <sortie.json>"""
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(RACINE / "experiments/instrument"), str(RACINE / "experiments/T3.0"),
                str(RACINE / "experiments/T3.1")]
import diag4
import oracle_niveau


def main():
    k, jeux, sortie = int(sys.argv[1]), sys.argv[2].split(","), Path(sys.argv[3])
    if k > 1:
        diag4.environnement = oracle_niveau.environnement_k(k)
    res = json.loads(sortie.read_text()) if sortie.exists() else {}
    for gid in jeux:
        t0 = time.time()
        grilles, acts = diag4.amorce(gid, 40, 0)
        tr = diag4.Trajectoire([g.tolist() for g in grilles], acts)
        th, _ = diag4.induire([(tr, None, None)], limite_s=diag4.LIMITE_S)
        diag4.LIMITE_S, diag4.LIMITE_REEL = 600, 1000000  # après l'induction : seule la recherche de C change
        try:
            r = diag4.config_C(gid, th, tr)
        finally:
            diag4.LIMITE_S, diag4.LIMITE_REEL = 120, 3000
        res[gid] = {"jeu": gid, "niveau": k, "C600": r, "secondes": round(time.time() - t0, 1)}
        print(gid, k, r.get("gagne"), r.get("raison"), flush=True)
        sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
