# SPDX-License-Identifier: MIT-0
"""Contrôle des FINS DE NIVEAU (CCM-068/123) [session B] : sur toutes les traces gagnantes (R0, parties de Claude, traces
BFS de A), la fin de niveau déclarée par `regles/<jeu>.json` tombe-t-elle EXACTEMENT sur les vrais changements de niveau
du moteur (0 manquée, 0 à tort) ? Comble l'angle mort de la non-régression, qui ne juge pas ces coups.
Usage : uv run python experiments/T3.1/au_dela/fins_niveau.py [jeux…]  → au_dela/fins_niveau.json"""
import json
import logging
import sys
from pathlib import Path

import numpy as np

RAC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAC / "experiments/T3.1"))
import mesure_exhaustivite as m
from arcengine.enums import GameAction
from fidelite import NUM, evenements

NOMS = {0: "RESET", 1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "CLICK", 7: "UNDO"}


def coups_trace(f):
    out = []
    for e in evenements(f):
        if "board" not in e or e.get("type") == "initial" or e.get("action_name", "") not in NUM:
            continue
        a = m.action_de(e)
        k = NUM[e["action_name"]]
        out.append((k, {"x": a[2], "y": a[1]} if k == 6 else None, a))
    return out


def coups_claude(f):
    out = []
    for c in json.loads(Path(f).read_text())["coups"]:
        a, d = c["a"], c.get("d") or {}
        out.append((a, {"x": d.get("x"), "y": d.get("y")} if a == 6 else None, (NOMS[a], d.get("y"), d.get("x"))))
    return out


def rejouer(arc, gid, coups, verbeux=False, depart=0):
    step, _ = m.charger_step(gid[:4])
    cv = bool(getattr(step, "canevas", False))
    env = arc.make(gid)
    env.reset()
    g = env._game
    if depart:
        g.set_level(depart)
    scene = m._resync(env, None, cv)
    cache = m._etat_cache(g)
    niveau = g._current_level_index
    r = {"reels": 0, "justes": 0, "manques": 0, "a_tort": 0, "exacts": 0, "coups": 0, "details": []}
    for i, (k, data, act) in enumerate(coups):
        obs = env.step(GameAction.from_id(k), data=data) if data else env.step(GameAction.from_id(k))
        if k == 0:
            scene, cache, niveau = m._resync(env, None, cv), m._etat_cache(g), g._current_level_index
            continue
        etat = obs.state.name if obs is not None else "?"
        change = g._current_level_index != niveau or etat == "WIN"
        perdu = etat == "GAME_OVER"
        _, image = m.scene_moteur(env)
        complet = np.asarray(obs.frame[-1], dtype=np.int16) if obs is not None and obs.frame else image
        sprites, cache2 = m.etat_moteur(env)
        vrai = {"image": image, "complet": complet, "sprites": sprites, "cache": cache2, "cache_change": cache2 != cache}
        cache = cache2
        scene.issue = None
        _, ok, err, _, _ = m.juger(scene, step, act, vrai, cv)
        decl = scene.issue in ("niveau", "victoire")
        if err:
            r["details"].append((i, "erreur", err))
        if change:
            r["reels"] += 1
            r["justes" if decl else "manques"] += 1
            if not decl or verbeux:
                r["details"].append((i, "manque" if not decl else "juste", niveau, act, scene.issue))
        elif decl:
            r["a_tort"] += 1
            r["details"].append((i, "a_tort", niveau, act, scene.issue))
        elif not perdu:
            r["coups"] += 1
            r["exacts"] += ok
        if change or perdu:
            scene, niveau = m._resync(env, None, cv), g._current_level_index
        elif not ok:
            scene = m._resync(env, scene, cv)
    r["details"] = r["details"][:12]
    return r


def main(jeux):
    logging.disable(logging.CRITICAL)
    arc = m.arcade()
    jeux = jeux or sorted(p.stem for p in (RAC / "experiments/T3.1/regles").glob("*.json") if "_" not in p.stem)
    out = []
    for j in jeux:
        gid = json.loads(next((RAC / "experiments/arc3/environment_files" / j).glob("*/metadata.json")).read_text())["game_id"]
        sources = [("R0", coups_trace(f)) for f in m.fichiers_traces([j])]
        c = RAC / f"experiments/claude_joue/parties/{j}.json"
        if c.exists():
            sources.append(("claude", coups_claude(c)))
        b = RAC / f"runs_pod/traces/{gid}_p0_events.jsonl"
        if b.exists():
            sources.append(("bfsA", coups_trace(b)))
        for nom, coups in sources:
            r = rejouer(arc, gid, coups)
            out.append({"jeu": j, "source": nom, **{k: v for k, v in r.items() if k != "details"}, "details": r["details"]})
            print(j, nom, f"reels={r['reels']} justes={r['justes']} manques={r['manques']} a_tort={r['a_tort']}",
                  f"(autres coups exacts {r['exacts']}/{r['coups']})", r["details"] if (r["manques"] or r["a_tort"]) else "", flush=True)


    (RAC / "experiments/T3.1/au_dela/fins_niveau.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print("TOTAL", "réels", sum(x["reels"] for x in out), "justes", sum(x["justes"] for x in out), "manqués",
          sum(x["manques"] for x in out), "à tort", sum(x["a_tort"] for x in out), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
