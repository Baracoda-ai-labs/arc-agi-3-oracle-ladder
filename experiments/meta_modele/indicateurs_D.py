# SPDX-License-Identifier: MIT-0
"""CW-321 (D) — classement des indicateurs de bord depuis les pixels (chrysalide/arc3/economie.py) sur les 20 jeux publics,
parties de Franzen rejouées en entier (traces de B, runs_pod/traces_niveaux, fichier du plus haut niveau), morts et
changements de niveau compris. Sortie JSON par jeu ; comparaison à experiments/meta_modele/audit.json (vérité de B).
Usage : uv run python experiments/meta_modele/indicateurs_D.py <sortie.json> [jeu ...]"""
import json
import sys
from pathlib import Path

import numpy as np
from arcengine.enums import GameAction, GameState

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE), str(RACINE / "experiments/perception_D")]


def partie(gid):
    import sortes_sprites as S

    from chrysalide.arc3.logique.jeux import environnement
    env = environnement(gid, RACINE / "experiments/arc3/environment_files")
    f = env.reset()
    gs, evs = [np.asarray(f.frame[-1])], []
    for num, r, c in S.actions(gid):
        n0 = f.levels_completed
        f = env.step(GameAction.ACTION6, data={"x": c, "y": r}) if num == 6 else env.step(GameAction.from_id(num))
        if f.state == GameState.WIN:
            break
        ev = "niveau" if f.levels_completed > n0 else "coup"
        if f.state == GameState.GAME_OVER:
            f, ev = env.step(GameAction.RESET), "mort"
        gs.append(np.asarray(f.frame[-1]))
        evs.append(ev)
    return gs, evs


def effets(gs, evs):
    out = []
    for t, _ in enumerate(evs):
        ch = gs[t] != gs[t + 1]
        ch[:3, :] = ch[-3:, :] = ch[:, :3] = ch[:, -3:] = False
        out.append(bool(ch.any()))
    return out


if __name__ == "__main__":
    import sortes_sprites as S

    from chrysalide.arc3.economie import classer
    sortie, jeux = sys.argv[1], sys.argv[2:] or S.JEUX
    verite = json.loads((RACINE / "experiments/meta_modele/audit.json").read_text())["jeux"]
    res = {}
    for g in jeux:
        gs, evs = partie(g)
        ind = classer(gs, evs, effets(gs, evs))
        ind.sort(key=lambda i: -(i["boite"][2] - i["boite"][0] + 1) * (i["boite"][3] - i["boite"][1] + 1))
        res[g] = {"coups": len(evs), "morts": evs.count("mort"), "niveaux": evs.count("niveau"),
                  "indicateurs": [{k: v for k, v in i.items() if k != "mesure"} for i in ind],
                  "verite": [(i["represente"], i["regle"][:120]) for i in verite[g]["lecture"]["interface"]]}
        print(g, res[g]["coups"], "coups", res[g]["morts"], "morts", res[g]["niveaux"], "niveaux", flush=True)
        for i in res[g]["indicateurs"][:6]:
            print("   ", i["boite"], f"c{i['couleur']}", i["etiquettes"], "; ".join(i["phrases"]))
        for v in res[g]["verite"]:
            print("    VRAI", v[0], "—", v[1])
    Path(sortie).write_text(json.dumps(res, ensure_ascii=False, indent=1))
