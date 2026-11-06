# SPDX-License-Identifier: MIT-0
"""CW-165/166 [session B] : traces « tous niveaux » pour le banc de PERCEPTION de C, avec les IMAGES INTERMÉDIAIRES
(« on travaille sur des films ») — une partie au hasard de N coups depuis le DÉBUT de chaque niveau atteint par R0.
Chaque fichier se rejoue depuis RESET : préfixe = coups de R0 jusqu'au 1er coup du niveau k, puis N coups au hasard
(actions offertes par le jeu ; clic sur un pixel au hasard). Format du harnais (`*_p0_events.jsonl`) : événement
« initial » puis un événement « action » par coup avec `board` (image finale), `frames` (TOUTES les images rendues
par le moteur pour ce coup), `level`, `game_over`, `level_completed`, `prefixe` (vrai pour les coups de R0).
Aucun témoin. Sortie : runs_pod/traces_niveaux/<gid>_niv<k>_p0_events.jsonl
Usage : uv run python experiments/T3.1/au_dela/traces_niveaux.py [coups par niveau=60] [jeux…]"""
import json
import logging
import random
import sys
from pathlib import Path

from arcengine.enums import GameAction

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import mesure_exhaustivite as m
from fidelite import NUM, evenements

SORTIE = m.DONNEES / "runs_pod/traces_niveaux"
NOMS = {0: "RESET", 1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "CLICK", 7: "UNDO"}


def jouer(env, a, r=None, c=None):
    return env.step(GameAction.from_id(a), data={"x": c, "y": r}) if a == 6 else env.step(GameAction.from_id(a))


def evt(obs, k, a, r, c, prefixe):
    frames = [f.tolist() if hasattr(f, "tolist") else f for f in (obs.frame or [])]
    disp = f"MOUSE(row={r}, col={c})" if a == 6 else NOMS[a]
    return {"type": "action", "action_name": f"ACTION{a}", "action_display": disp, "action_num": k,
            "board": frames[-1] if frames else None, "frames": frames, "level": obs.levels_completed + 1,
            "game_over": obs.state.name == "GAME_OVER", "level_completed": False, "state": obs.state.name,
            "prefixe": prefixe}


def main(coups=60, *jeux):
    logging.disable(logging.CRITICAL)
    SORTIE.mkdir(parents=True, exist_ok=True)
    arc, rnd, bilan = m.arcade(), random.Random(0), {}
    for f in m.fichiers_traces(jeux or None):
        gid = f.name.split("_p")[0]
        r0 = [e for e in evenements(f) if e.get("type") == "action" and e.get("action_name", "") in NUM]
        niveaux = sorted({int(e.get("level", 1)) for e in r0})
        bilan[gid] = []
        for k in niveaux:
            env = arc.make(gid)
            obs = env.reset()
            out = [{"type": "initial", "board": obs.frame[-1].tolist() if hasattr(obs.frame[-1], "tolist") else obs.frame[-1],
                    "level": 1, "action_display": "RESET"}]
            n = 0
            for e in r0:  # préfixe : coups de R0 jusqu'à ce que le MOTEUR soit au niveau k
                if obs.levels_completed + 1 >= k:
                    break
                a = m.action_de(e)
                num = NUM[e["action_name"]]
                obs = jouer(env, num, a[1], a[2])
                n += 1
                out.append(evt(obs, n, num, a[1], a[2], True))
            if obs.levels_completed + 1 != k:
                bilan[gid].append({"niveau": k, "erreur": "préfixe R0 n'atteint pas ce niveau"})
                continue
            offertes = [a for a in env._game._available_actions if a in NOMS and a not in (0, 7)]
            joues = 0
            while joues < int(coups):
                a = rnd.choice(offertes)
                r, c = (rnd.randrange(64), rnd.randrange(64)) if a == 6 else (None, None)
                avant = obs.levels_completed
                obs = jouer(env, a, r, c)
                n += 1
                joues += 1
                ev = evt(obs, n, a, r, c, False)
                ev["level_completed"] = obs.levels_completed > avant
                out.append(ev)
                if obs.state.name in ("GAME_OVER", "WIN") or obs.levels_completed > avant:
                    break  # fin de niveau ou de partie : la suite serait un autre niveau
            nom = SORTIE / f"{gid}_niv{k}_p0_events.jsonl"
            nom.write_text("\n".join(json.dumps(x) for x in out) + "\n")
            bilan[gid].append({"niveau": k, "prefixe": n - joues, "hasard": joues, "fichier": nom.name})
        print(gid, [(b["niveau"], b.get("hasard", b.get("erreur"))) for b in bilan[gid]], flush=True)
    (SORTIE / "bilan.json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
