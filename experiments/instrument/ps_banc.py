# SPDX-License-Identifier: MIT-0
"""Banc PuzzleScript (CW-229, 3ᵉ source du moteur seul) : `experiments/T4/banc_export.py` de D (même mesure que T4 : chaîne
de C sur l'historique de la solution, coup gagnant retiré), enveloppé pour la robustesse. Un processus neuf par jeu, délai
dur par jeu (un jeu qui plante ou dépasse est compté « échec d'exécution », pas perdu), sortie réécrite après CHAQUE jeu.
Usage : uv run python experiments/instrument/ps_banc.py <environment_files> <sortie.json> [budget_s=30] [processus=6] [delai_s=1800]"""
import json
import sys
import time
from multiprocessing import get_context
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "experiments/T4"))
import banc_export as BE


def _empreinte(f):
    """CW-255 : version du moteur PuzzleScript de référence (corrigé par E en 8762746), notée dans chaque sortie."""
    import hashlib
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()[:16] if Path(f).exists() else None


def main(envs, sortie, budget=30.0, proc=6, delai=1800):
    ids = sorted(json.loads(p.read_text())["game_id"] for p in Path(envs).glob("*/*/metadata.json"))
    t0, jeux, sortie = time.monotonic(), {}, Path(sortie)
    if sortie.exists():  # reprise : les jeux déjà mesurés (hors échecs d'exécution) sont gardés
        jeux = {j["jeu"]: j for j in json.loads(sortie.read_text())["jeux"] if "echec_execution" not in j}
        ids = [g for g in ids if g not in jeux]
    ctx = get_context("spawn")
    with ctx.Pool(int(proc), maxtasksperchild=1) as pool:
        attente = {g: pool.apply_async(BE.un, ((envs, g, float(budget)),)) for g in ids}
        for g, a in attente.items():
            try:
                r = a.get(timeout=float(delai))
            except Exception as e:  # noqa: BLE001 — délai dépassé ou processus mort : échec compté
                r = {"jeu": g, "niveaux": [], "echec_execution": f"{type(e).__name__}: {e}"[:200]}
            jeux[g] = r
            n, refus = BE.resume(list(jeux.values()))
            sortie.write_text(json.dumps({"budget_s": float(budget), "s": round(time.monotonic() - t0, 1), "resume": n,
                                          "psmoteur_sha256": _empreinte(RACINE / "experiments/banc_ps/psmoteur.py"),
                                          "echecs_execution": sorted(k for k, v in jeux.items() if "echec_execution" in v),
                                          "refus": refus, "jeux": [jeux[k] for k in sorted(jeux)]}, ensure_ascii=False, indent=1))
            print(g, len(r["niveaux"]), r.get("echec_execution", ""), flush=True)
    print(n, refus)


if __name__ == "__main__":
    main(*sys.argv[1:])
