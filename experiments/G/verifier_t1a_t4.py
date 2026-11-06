"""[G] CW-455/456 T1a sur T4 : rejoue dans le VRAI jeu (depuis RESET) chaque plan de la précondition de C sur T4
(`experiments/G/log_t1a_t4_<passage>.txt`), avec son vérificateur tel quel (`experiments/T1_releve_p1/verifier_plans.py`,
`T1_FENETRE=40`, `CHRYS_BUT_SUPPOSE=1`). Usage : verifier_t1a_t4.py <passage> [processus=4] → lignes JSON"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

R = Path(__file__).resolve().parents[2]
T4 = R / "experiments/T4/jeux/t4/environment_files"


def un(passage, d):
    env = {**os.environ, "PYTHONPATH": str(R), "T1_FENETRE": "40", "CHRYS_BUT_SUPPOSE": "1"}
    r = subprocess.run([str(R / ".venv/bin/python"), str(R / "experiments/T1_releve_p1/verifier_plans.py"),
                        str(R / "experiments/films_p1/combo_t4" / passage), d["jeu"], str(d["niveau"]), str(d["k"]), str(T4)],
                       capture_output=True, text=True, env=env, timeout=600, check=False)
    lignes = [x for x in r.stdout.splitlines() if x.startswith("{")]
    return {"jeu": d["jeu"], "niveau": d["niveau"], "k": d["k"], "plan": d["plan"], "origine": d.get("origine"),
            "verif": json.loads(lignes[-1]) if lignes else {"erreur": r.stderr[-300:]}}


def main():
    passage = sys.argv[1]
    proc = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    plans = [json.loads(x) for x in (R / f"experiments/G/log_t1a_t4_{passage}.txt").read_text().splitlines()
             if x.startswith("{") and '"plan": ' in x and '"plan": null' not in x and '"k"' in x]
    with ThreadPoolExecutor(proc) as ex:
        for r in ex.map(lambda d: un(passage, d), plans):
            print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
