# SPDX-License-Identifier: MIT-0
"""SUR LE POD (CW-098.4), en parallèle des blocs GPU, sur les CPU libres : traces de TOUS les niveaux des 20 jeux non témoins,
par recherche en largeur dans le vrai moteur (chrysalide/arc3/recherche.py). Un processus par jeu, priorité basse.
Usage : nice -n 19 python scripts/pod/traces_tous.py <environment_files> <sortie> [plafond_s_par_niveau] [memoire_Go_totale]
La mémoire totale (défaut 120 Go) est partagée entre les processus : chacun garde des copies du jeu en file tant que
son quota le permet, puis passe en mode « chemin » (rejoue depuis la racine) ; file plafonnée à 300 000 nœuds."""
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


def un(args):
    envs, sortie, gid, plafond, memoire_mo = args
    from arc_agi import Arcade, OperationMode

    from chrysalide.arc3.recherche import traces_jeu
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs)
    try:
        ev, bilan = traces_jeu(arc, gid, plafond_s=plafond, plafond_noeuds=2_000_000, max_file=300_000,
                               memoire_mo=memoire_mo)
    except Exception as x:  # noqa: BLE001
        ev, bilan = [], [{"erreur": f"{type(x).__name__}: {x}"[:200]}]
    Path(sortie, f"{gid}_p0_events.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
    Path(sortie, f"{gid}_bilan.json").write_text(json.dumps(bilan, ensure_ascii=False))
    return gid, bilan


if __name__ == "__main__":
    envs, sortie = sys.argv[1], sys.argv[2]
    plafond = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    memoire_go = float(sys.argv[4]) if len(sys.argv) > 4 else 120.0
    Path(sortie).mkdir(parents=True, exist_ok=True)
    from arc_agi import Arcade, OperationMode
    ids = sorted(e.game_id for e in Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs).get_environments()
                 if e.game_id[:4] not in TEMOINS)
    # quota par processus : la part des copies (le reste — empreintes, arbre, Python — est compté à 40 %)
    n_proc = min(len(ids), int(os.environ.get("TRACES_PROC", "6")))  # leçon FC2 : peu de processus sur le pod
    memoire_mo = 0.6 * memoire_go * 1000 / n_proc
    with Pool(n_proc) as p:
        for gid, bilan in p.imap_unordered(un, [(envs, sortie, g, plafond, memoire_mo) for g in ids]):
            print(gid[:4], json.dumps(bilan, ensure_ascii=False), flush=True)
