# SPDX-License-Identifier: MIT-0
"""Test plafond « budget ×100 » (CW-305, A) : un niveau frontière, un bras, à règles exactes, depuis le début du niveau
atteint par le préfixe corrigé (`prefixes_r0.json`, comme `banc_rates`). Bras : `but` (référence de `plafonds`, meilleur
d'abord), `sous_buts` (défi 6 sans macros), `profondeur` (« clé seule », `plan_langage`). Pas de plafond de nœuds ; budget
en secondes ; garde mémoire : au-delà de MEMOIRE_GO de mémoire résidente, arrêt noté « mémoire » (raison à part).
La courbe « gagné selon le budget » se lit sur `t_victoire` ; un relevé (temps, mémoire) toutes les 60 s va dans <sortie>.log.
Usage : uv run python experiments/instrument/budget100.py <jeu> <niveau> <bras> <secondes> <sortie.json> [memoire_go=8]"""
import json
import os
import resource
import sys
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]


def rss_go():
    if os.path.exists("/proc/self/status"):  # pod (Linux) : mémoire résidente actuelle
        with open("/proc/self/status") as f:
            for ligne in f:
                if ligne.startswith("VmRSS:"):
                    return int(ligne.split()[1]) / 2**20
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30  # macOS : maximum, en octets


def main(gid, k, bras, secondes, sortie, memoire_go=8):
    k, secondes, memoire_go = int(k), float(secondes), float(memoire_go)
    sortie = Path(sortie)
    out = {"jeu": gid, "niveau": k, "bras": bras, "budget_s": secondes, "memoire_go": memoire_go,
           "backend": os.environ.get("CHRYS_BACKEND_TABLEAUX", "1")}
    t0 = time.time()
    journal = open(f"{sortie}.log", "a")  # noqa: SIM115 (fil de garde jusqu'à la fin)
    mem_max = [0.0]

    def garde():
        while True:
            m = rss_go()
            mem_max[0] = max(mem_max[0], m)
            journal.write(json.dumps({"t": round(time.time() - t0), "rss_go": round(m, 2)}) + "\n")
            journal.flush()
            if m > memoire_go:
                out.update(raison="mémoire", t_arret=round(time.time() - t0, 1), memoire_max_go=round(mem_max[0], 2))
                sortie.write_text(json.dumps(out, indent=1, ensure_ascii=False))
                os._exit(3)
            time.sleep(min(60, max(5, secondes / 1000)))
    threading.Thread(target=garde, daemon=True).start()

    import plafonds
    pre = json.loads((RACINE / "experiments/instrument/prefixes_r0.json").read_text()).get(gid, {}).get(str(k))
    if pre is not None:  # même remplacement que banc_rates : début du niveau k atteint par le préfixe vérifié (RESET compris)
        _orig = plafonds.env_au_niveau

        def env_au_niveau(g, kk):
            if (g, kk) != (gid, k):
                return _orig(g, kk)
            from arcengine.enums import GameAction
            from mesure_exhaustivite import arcade
            env = arcade().make(g)
            f = env.reset()
            for c in pre:
                f = env.step(GameAction.RESET) if c[0] == 0 else plafonds.jouer(env, tuple(c))
                if f is not None and f.state.name == "GAME_OVER":
                    f = env.step(GameAction.RESET)
            return (env, f) if f is not None and f.levels_completed == kk - 1 else (None, None)
        plafonds.env_au_niveau = env_au_niveau
    out["prefixe"] = "prefixes_r0.json" if pre is not None else "plafonds.prefixe"
    if bras == "sous_buts":
        sys.path.insert(0, str(RACINE / "experiments/instrument"))
        import banc_rates
        r = banc_rates.sous_buts(plafonds, gid, k, 10**12, secondes)  # planificateur générique, plan rejoué en vrai jeu
    else:
        r = plafonds.p0(gid, k, 10**12, secondes, "but" if bras == "but" else "langage_profondeur")
    out.update({x: r.get(x) for x in ("gagne", "plan", "noeuds", "etats", "raison", "profondeur", "table")})
    out.update(t_victoire=round(time.time() - t0, 1) if r.get("gagne") else None, duree_s=round(time.time() - t0, 1),
               memoire_max_go=round(max(mem_max[0], rss_go()), 2))
    sortie.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(out, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
