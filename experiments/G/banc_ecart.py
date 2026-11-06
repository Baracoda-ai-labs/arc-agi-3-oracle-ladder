"""[G] CW-337.1, preuve A : par niveau d'un jeu T4 (chargement et préfixe comme `experiments/T4/banc_t4.py` : les
solutions de `verite.json` servent seulement à ATTEINDRE le niveau k), la recherche de référence (`resoudre_niveau`,
largeur dans le vrai moteur) contre `macro_moteur.chercher_moteur` (algorithme gelé de macro_g, vrai moteur), même
budget de temps. Les deux sont exactes par construction (le moteur est le simulateur). Échecs comptés.
Lot tenu à l'écart : `CHRYS_ECART=1` et garde de B (`experiments/verrou/garde.py`) appelée AVANT toute ouverture.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_ecart.py <environment_files> <sortie.json> [secondes=300] [jeux…]"""
import json
import sys
import time
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE), str(RACINE / "experiments/G"), str(RACINE / "experiments/T4"), str(RACINE / "experiments/verrou")]


def main():
    envs, sortie = sys.argv[1], Path(sys.argv[2])
    secondes = float(sys.argv[3]) if len(sys.argv) > 3 else 300
    from garde import verifier
    verifier(chemin=envs)  # lève Verrouille si le dossier est fermé (verrou du 27, lot à l'écart sans CHRYS_ECART=1)
    from arc_agi import Arcade, OperationMode
    from arcengine.enums import GameState
    from banc_t4 import _coup_solution, _image
    from macro_moteur import chercher_moteur

    from chrysalide.arc3.recherche import resoudre_niveau
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs)
    metas = sorted(Path(envs).glob("*/*/metadata.json"))
    jeux = sys.argv[4:] or [json.loads(m.read_text())["game_id"] for m in metas]
    res = []
    for gid in jeux:
        verifier(chemin=envs, jeu=gid)
        meta = next(m for m in metas if json.loads(m.read_text())["game_id"].split("-")[0] == gid.split("-")[0])
        v = json.loads((meta.parent / "verite.json").read_text())
        env = arc.make(gid)
        fr = env.reset()
        jeu, image = env._game, _image(fr)
        for k, niv in enumerate(v["niveaux"]):
            ligne = {"jeu": gid, "niveau": k + 1, "mecaniques": v["mecaniques"], "optimum": len(niv["solution"])}
            if jeu._current_level_index != k:
                ligne["erreur"] = "préfixe non conforme"
                res.append(ligne)
                break
            t0 = time.process_time()
            try:
                ch, _h, _im, statut, inf = resoudre_niveau(jeu, np.asarray(image), secondes, 10 ** 9)
                ligne["reference"] = {"gagne": ch is not None, "coups": len(ch) if ch else None, "statut": statut,
                                      "noeuds": inf.get("noeuds"), "cpu": round(time.process_time() - t0, 1)}
            except Exception as e:  # noqa: BLE001
                ligne["reference"] = {"gagne": False, "erreur": f"{type(e).__name__}: {e}"[:160]}
            t0 = time.process_time()
            try:
                r = chercher_moteur(jeu, np.asarray(image), 20000, secondes)
                ligne["macro"] = {"gagne": r["plan"] is not None, "coups": r["long_plan"], "arret": r["arret"],
                                  "cle": r.get("cle"), "etats_hauts": r["etats_hauts"],
                                  "cpu": round(time.process_time() - t0, 1)}
            except Exception as e:  # noqa: BLE001
                ligne["macro"] = {"gagne": False, "erreur": f"{type(e).__name__}: {e}"[:160]}
            res.append(ligne)
            print(json.dumps(ligne, ensure_ascii=False), flush=True)
            sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False))
            for a in niv["solution"]:  # préfixe : la solution de la vérité, seulement pour atteindre le niveau suivant
                fr = jeu.perform_action(_coup_solution(a, niv)[0], raw=True)
            image = _image(fr)
            if fr.state == GameState.WIN:
                break
    n = len(res)
    print(f"niveaux {n} ; référence {sum(bool(x.get('reference', {}).get('gagne')) for x in res)} ; "
          f"macro {sum(bool(x.get('macro', {}).get('gagne')) for x in res)} ; "
          f"macro seule {sum(bool(x.get('macro', {}).get('gagne')) and not x.get('reference', {}).get('gagne') for x in res)} ; "
          f"référence seule {sum(bool(x.get('reference', {}).get('gagne')) and not x.get('macro', {}).get('gagne') for x in res)}")


if __name__ == "__main__":
    main()
