# SPDX-License-Identifier: MIT-0
"""Transfert du but appris vers le niveau k+1 (CW-320, CCM-035-E) : moteur réel seul (boucle de `banc_rates`), départ au début
du niveau k+1 par le préfixe de Franzen R0, 10 min, apparié AVEC et SANS `CHRYS_BUTS=<fichier de E>`. Mêmes réglages que la
mesure des frontières (PARTIEL=2, AMODAL, BUT_SUPPOSE, budget 2 s), posés par le lanceur.
Usage : uv run python experiments/instrument/banc_k1.py <jeu> <niveau> <avec|sans> <sortie.json> [minutes=10]"""
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1"), str(RACINE / "experiments/instrument")]


def main(gid, k, cond, sortie, minutes=10):
    k, minutes = int(k), float(minutes)
    os.environ["CHRYS_MOTEUR"] = "1"
    f = RACINE / "experiments/E_franzen/buts_appris_c" / f"{gid}_N{k}.json"
    if cond == "avec":
        os.environ["CHRYS_BUTS"] = str(f)
    else:
        os.environ.pop("CHRYS_BUTS", None)
    import banc_rates
    import plafonds
    pre = plafonds.prefixe(gid, k)
    out = {"jeu": gid, "niveau": k, "condition": cond, "buts": json.loads(f.read_text()) if cond == "avec" else None,
           "prefixe": None if pre is None else len(pre)}
    if pre is not None:
        banc = banc_rates._banc_moteur_seul()
        mot = banc.jouer(gid, "rates", minutes, 0, Path(sortie).parent / "traces", prefixe=pre)
        out["moteur"] = {x: mot.get(x) for x in ("niveau_depart", "niveaux", "niveaux_coup_final_moteur", "coups", "refus",
                                                  "duree_s")}
        out["moteur"]["bilan"] = {x: v for x, v in (mot.get("bilan") or {}).items() if isinstance(v, (int, float))}
        out["entonnoir"] = banc_rates.entonnoir(out["moteur"])
    Path(sortie).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({x: out.get(x) for x in ("jeu", "niveau", "condition", "prefixe", "entonnoir")}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
