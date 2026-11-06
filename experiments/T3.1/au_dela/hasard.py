# SPDX-License-Identifier: MIT-0
"""Faille 2 du banc, version générale [session B] : chaque `regles/<jeu>.json` est jugée sur TOUS les niveaux du jeu,
par des coups au hasard joués dans le vrai moteur à partir du début de chaque niveau (set_level), avec la même
fonction de jugement honnête que le banc (`mesure_exhaustivite.juger`, image + état des sprites + état caché).
Une transition fausse fait resynchroniser la scène (comme le banc) ; fin de niveau, défaite ou RESET : retour au début du
niveau. Les coups d'un niveau qu'aucune trace ne visite testent la GÉNÉRALITÉ des règles (niveaux inédits pour elles).
Usage : uv run python experiments/T3.1/au_dela/hasard.py [coups par niveau=60] [jeux…]  → au_dela/hasard.json"""
import json
import logging
import random
import sys
from pathlib import Path

import numpy as np
from arcengine.enums import GameAction

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import mesure_exhaustivite as m

NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "CLICK", 7: "UNDO"}


def vrai_apres(env, obs, cache_avant):
    _, image = m.scene_moteur(env)
    complet = np.asarray(obs.frame[-1], dtype=np.int16) if obs is not None and obs.frame else image
    sprites, cache = m.etat_moteur(env)
    return {"image": image, "complet": complet, "sprites": sprites, "cache": cache, "cache_change": cache != cache_avant}


def depart(env, i, cv=False):
    env.reset()
    env._game.set_level(i)
    return m._resync(env, None, canevas=cv), m._resync(env, None, canevas=cv), m._etat_cache(env._game)


def jeu(arc, j, coups, rnd):
    step, source = m.charger_step(j)
    cv = bool(getattr(step, "canevas", False))
    meta = json.loads(next((m.DONNEES / "experiments/arc3/environment_files" / j).glob("*/metadata.json")).read_text())
    env = arc.make(meta["game_id"])
    env.reset()
    g = env._game
    actions = [a for a in g._available_actions if a in NOMS]
    par_niveau = []
    for i in range(len(g._levels)):
        try:
            scene, temoin, cache = depart(env, i, cv)
        except Exception as ex:  # noqa: BLE001 — signalé
            par_niveau.append({"niveau": i + 1, "erreur": f"{type(ex).__name__}: {str(ex)[:80]}"})
            continue
        n = ok = t_ok = 0
        premiere = None
        while n < coups:
            a = rnd.choice(actions)
            r, c = (rnd.randrange(64), rnd.randrange(64)) if a == 6 else (None, None)
            act = (NOMS[a], r, c)
            obs = env.step(GameAction.from_id(a), data={"x": c, "y": r}) if a == 6 else env.step(GameAction.from_id(a))
            if obs is None or g._current_level_index != i or obs.state.name in ("GAME_OVER", "WIN"):
                scene, temoin, cache = depart(env, i, cv)  # coup de fin de niveau ou de défaite : non jugé (comme le banc)
                continue
            vrai = vrai_apres(env, obs, cache)
            cache = vrai["cache"]
            _, juste, erreur, faux, _ = m.juger(scene, step, act, vrai, complet=cv)
            t_juste = m.juger(temoin, None, act, vrai, complet=cv)[1]  # témoin « rien ne change » (identité), comme au banc
            n, ok, t_ok = n + 1, ok + juste, t_ok + t_juste
            if not t_juste:
                temoin = m._resync(env, None, canevas=cv)
            if not juste:
                premiere = premiere or {"coup": n, "action": act, "erreur": erreur, "pixels_faux": faux}
                scene = m._resync(env, scene, canevas=cv)
        par_niveau.append({"niveau": i + 1, "coups": n, "exacts": ok, "temoin": t_ok, "premiere_erreur": premiere})
    return {"jeu": j, "source": source, "niveaux": par_niveau,
            "exacts": sum(x.get("exacts", 0) for x in par_niveau), "coups": sum(x.get("coups", 0) for x in par_niveau),
            "temoin": sum(x.get("temoin", 0) for x in par_niveau)}


def main(coups=60, *jeux):
    logging.disable(logging.CRITICAL)
    arc, rnd, res = m.arcade(), random.Random(0), []
    for f in sorted((ICI.parent / "regles").glob("*.json")):
        j = f.stem
        if jeux and j not in jeux:
            continue
        try:
            r = jeu(arc, j, int(coups), rnd)
        except Exception as ex:  # noqa: BLE001 — signalé et compté
            r = {"jeu": j, "erreur": f"{type(ex).__name__}: {str(ex)[:120]}"}
        res.append(r)
        print(j, r.get("exacts"), "/", r.get("coups"), "témoin", r.get("temoin"),
              [f"{x['niveau']}:{x.get('exacts')}/{x.get('coups')}(t{x.get('temoin')})"
                                                       for x in r.get("niveaux", [])], r.get("erreur", ""), flush=True)
    (ICI / "hasard.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
