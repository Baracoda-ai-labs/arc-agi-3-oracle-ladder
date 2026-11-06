# SPDX-License-Identifier: MIT-0
"""CW-171/176/179 [session B] : vérification des `regles/<jeu>.json` sur les PARTIES GAGNANTES jouées par Claude
(`experiments/claude_joue/parties/<jeu>.json`, coups {"a": action, "d": {"x", "y"}}), qui vont souvent plus loin que R0.
Même jugement honnête que le banc (`mesure_exhaustivite.juger` : image + état des sprites + état caché ; image complète
si le programme emploie le canevas) et même témoin « rien ne change ». Coups de fin de niveau / de partie non jugés.
Usage : uv run python experiments/T3.1/au_dela/claude_parties.py [jeux…]  → au_dela/claude_parties.json"""
import json
import logging
import sys
from pathlib import Path

import numpy as np
from arcengine.enums import GameAction

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import mesure_exhaustivite as m

PARTIES = m.DONNEES / "experiments/claude_joue/parties"
NOMS = {0: "RESET", 1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "CLICK", 7: "UNDO"}


def jeu(arc, f):
    j = f.stem
    step, source = m.charger_step(j)
    cv = bool(getattr(step, "canevas", False))  # programme à canevas : image complète, interface comprise (comme le banc)
    meta = json.loads(next((m.DONNEES / "experiments/arc3/environment_files" / j).glob("*/metadata.json")).read_text())
    env = arc.make(meta["game_id"])
    env.reset()
    g = env._game
    scene, temoin, cache = m._resync(env, None, canevas=cv), m._resync(env, None, canevas=cv), m._etat_cache(g)
    niveau = g._current_level_index
    par = {}
    for c in json.loads(f.read_text())["coups"]:
        a, d = c["a"], c.get("d") or {}
        r, col = d.get("y"), d.get("x")
        obs = env.step(GameAction.from_id(a), data={"x": col, "y": r}) if a == 6 else env.step(GameAction.from_id(a))
        if obs is None or a == 0 or g._current_level_index != niveau or obs.state.name in ("GAME_OVER", "WIN"):
            scene, temoin, cache = m._resync(env, None, canevas=cv), m._resync(env, None, canevas=cv), m._etat_cache(g)
            niveau = g._current_level_index
            continue
        _, image = m.scene_moteur(env)
        complet = np.asarray(obs.frame[-1], dtype=np.int16) if obs.frame else image
        sprites, cache2 = m.etat_moteur(env)
        vrai = {"image": image, "complet": complet, "sprites": sprites, "cache": cache2, "cache_change": cache2 != cache}
        cache = cache2
        act = (NOMS[a], r, col)
        _, ok, erreur, faux, _ = m.juger(scene, step, act, vrai, complet=cv)
        t_ok = m.juger(temoin, None, act, vrai, complet=cv)[1]
        p = par.setdefault(niveau + 1, {"coups": 0, "exacts": 0, "temoin": 0, "premiere_erreur": None})
        p["coups"] += 1
        p["exacts"] += ok
        p["temoin"] += t_ok
        if not ok:
            p["premiere_erreur"] = p["premiere_erreur"] or {"action": act, "erreur": erreur, "pixels_faux": faux}
            scene = m._resync(env, scene, canevas=cv)
        if not t_ok:
            temoin = m._resync(env, None, canevas=cv)
    return {"jeu": j, "source": source, "niveaux": par, "exacts": sum(p["exacts"] for p in par.values()),
            "coups": sum(p["coups"] for p in par.values()), "temoin": sum(p["temoin"] for p in par.values())}


def main(*jeux):
    logging.disable(logging.CRITICAL)
    arc, res = m.arcade(), []
    for f in sorted(PARTIES.glob("*.json")):
        if f.stem in m.TEMOINS or (jeux and f.stem not in jeux):
            continue
        try:
            r = jeu(arc, f)
        except Exception as ex:  # noqa: BLE001 — signalé et compté
            r = {"jeu": f.stem, "erreur": f"{type(ex).__name__}: {str(ex)[:150]}"}
        res.append(r)
        print(r["jeu"], r.get("exacts"), "/", r.get("coups"), "témoin", r.get("temoin"),
              {k: f"{v['exacts']}/{v['coups']}" for k, v in r.get("niveaux", {}).items()}, r.get("erreur", ""), flush=True)
    (ICI / "claude_parties.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
