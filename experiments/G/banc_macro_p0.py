"""[G] CW-330 (preuve A) : `macro_g` sur P0 (20 jeux × N1-3, programmes exacts corrigés de B) ; plans rejoués dans le vrai
jeu ; temps CPU. Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_macro_p0.py PROCESSUS [etats_hauts] [secondes]"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_portefeuille import RACINE, TEMOINS, _init


def _tache(t):
    import macro_g
    try:
        return macro_g.chercher(*t)
    except Exception as e:  # noqa: BLE001 — échec compté
        return {"jeu": t[0], "niveau": t[1], "arret": f"erreur {type(e).__name__}: {e}"[:160]}


def main():
    proc = int(sys.argv[1])
    eh, sec = (int(sys.argv[2]) if len(sys.argv) > 2 else 20000), (float(sys.argv[3]) if len(sys.argv) > 3 else 300)
    jeux = [p.stem for p in sorted((RACINE / "experiments/T3.1/regles").glob("*.json"))
            if "_" not in p.stem and p.stem not in TEMOINS]
    with Pool(proc, initializer=_init) as pool:
        res = []
        for r in pool.imap_unordered(_tache, [(j, k, eh, sec) for j in jeux for k in (1, 2, 3)], chunksize=1):
            res.append(r)
            print(json.dumps({x: r.get(x) for x in ("jeu", "niveau", "arret", "plan", "gagne", "cpu")}), flush=True)
    import subprocess
    version = subprocess.run(["git", "log", "-1", "--format=%h", "--", "experiments/T3.1/regles"], capture_output=True,
                             text=True, cwd=RACINE).stdout.strip()
    (RACINE / "experiments/G/macro_p0.json").write_text(json.dumps({"programmes": version, "resultats": res}, indent=1,
                                                                   default=str))
    print("gagnés", sum(bool(r.get("gagne")) for r in res), "sur", len(res), "programmes", version)


if __name__ == "__main__":
    main()
