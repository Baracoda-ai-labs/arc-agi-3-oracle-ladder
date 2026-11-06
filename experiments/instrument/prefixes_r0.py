# SPDX-License-Identifier: MIT-0
"""Préfixes Franzen R0 régénérés (CW-275) : TOUS les coups du passage R0 (morts et relances comprises), depuis le début
de la partie jusqu'à l'action qui finit le niveau k−1. Vérifiés par rejeu dans le vrai jeu (relance après game over, comme
`plafonds.env_au_niveau`). → experiments/instrument/prefixes_r0.json {jeu: {k: [(num, ligne, colonne)]}} (n'écrase pas
experiments/T3.0/prefixes_niveaux.json). Usage : uv run python experiments/instrument/prefixes_r0.py jeu:k …"""
import glob
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
R0 = min(glob.glob(str(RACINE / "runs_pod/R0/*/artifacts")))


def coups_jusqua(gid, k):
    f = next(Path(R0).glob(f"{gid}-*_events.jsonl"))
    out, apres_mort = [], False
    for ligne in f.read_text().splitlines():
        e = json.loads(ligne)
        if e.get("type") != "action":
            continue
        if e["action_name"] == "RESET":  # relance : celle qui suit une mort est déjà faite par le rejeu (comme le harnais)
            if not apres_mort:
                out.append((0, None, None))  # relance volontaire du niveau, rejouée telle quelle
            apres_mort = False
            continue
        apres_mort = bool(e.get("game_over"))
        num = int(e["action_name"].replace("ACTION", ""))
        if num == 6:
            aff = e["action_display"]
            r, c = (int(x.split("=")[1]) for x in aff[aff.index("(") + 1:-1].split(", "))
            out.append((6, r, c))
        else:
            out.append((num, None, None))
        if e.get("level_completed") and int(e.get("level", 0)) - 1 == k - 1:
            return out
    return None


def verifier(gid, k, pre):
    import plafonds
    from arcengine.enums import GameAction
    from mesure_exhaustivite import arcade
    env = arcade().make(gid)
    f = env.reset()
    for c in pre:
        f = env.step(GameAction.RESET) if c[0] == 0 else plafonds.jouer(env, c)
        if f is not None and f.state.name == "GAME_OVER":
            f = env.step(GameAction.RESET)
    return f is not None and f.levels_completed == k - 1


def main(*args):
    sortie = RACINE / "experiments/instrument/prefixes_r0.json"
    res = json.loads(sortie.read_text()) if sortie.exists() else {}
    for a in args:
        gid, k = a.split(":")
        k = int(k)
        pre = coups_jusqua(gid, k)
        ok = pre is not None and verifier(gid, k, pre)
        print(gid, k, None if pre is None else len(pre), "atteint" if ok else "NON ATTEINT")
        if ok:
            res.setdefault(gid, {})[str(k)] = pre
    sortie.write_text(json.dumps(res))


if __name__ == "__main__":
    main(*sys.argv[1:])
