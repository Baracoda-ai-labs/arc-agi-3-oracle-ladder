# SPDX-License-Identifier: MIT-0
"""CW-279 : vérification INDÉPENDANTE des plans du défi 6 : chaque plan (`solution` de plans/*_actions.json) est joué dans le
vrai jeu depuis NOTRE préfixe (prefixes_r0.json vérifié, sinon plafonds.env_au_niveau), avec notre code ; niveau gagné ?"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
PLANS = RACINE / "experiments/defi_llm/reponse_gpt6/defi6_intermediaire/plans"


def main():
    import plafonds
    from arcengine.enums import GameAction
    from mesure_exhaustivite import arcade
    r0 = json.loads((RACINE / "experiments/instrument/prefixes_r0.json").read_text())
    for f in sorted(PLANS.glob("*_actions.json")):
        d = json.loads(f.read_text())
        g, k = d["jeu"], int(d["niveau"])
        pre = [tuple(c) for c in r0.get(g, {}).get(str(k), [])] if str(k) in r0.get(g, {}) else plafonds.prefixe(g, k) or []
        env = arcade().make(g)
        fr = env.reset()
        for c in pre:
            fr = env.step(GameAction.RESET) if c[0] == 0 else plafonds.jouer(env, tuple(c))
            if fr is not None and fr.state.name == "GAME_OVER":
                fr = env.step(GameAction.RESET)
        depart = fr.levels_completed
        n = 0
        for c in d["solution"]:
            fr = plafonds.jouer(env, tuple(c))
            n += 1
            if fr.levels_completed >= k or fr.state.name in ("WIN", "GAME_OVER"):
                break
        ok = fr.levels_completed >= k or fr.state.name == "WIN"
        print(g, f"N{k}", "préfixe", len(pre), "départ", depart, "coups", n, "/", len(d["solution"]),
              "GAGNÉ" if ok else f"NON ({fr.state.name}, niveaux {fr.levels_completed})", "même préfixe que ChatGPT" if [list(x) for x in pre] == d["prefixe"] else "préfixe différent")


if __name__ == "__main__":
    main()
