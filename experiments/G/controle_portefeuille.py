"""[G] CW-429, contrôle F-C2 du module `chrysalide/arc3/logique/portefeuille_g.py` : sur P0 (règles exactes, départ du
moteur `_resync`, coups = actions + clics de l'image de départ), il doit reproduire le portefeuille mesuré
(`couche6_p0_30s.jsonl` : 18/60) ; plans rejoués dans le vrai jeu. Usage : controle_portefeuille.py [jeu:niveau,…] [s=60]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_p0 import _init


def un(gid, k, sec):
    import plafonds as pf
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import utilise_canevas
    from chrysalide.arc3.logique.portefeuille_g import portefeuille
    texte = json.loads((pf.REGLES / f"{gid}.json").read_text())
    env, fr = pf.env_au_niveau(gid, k)
    if env is None:
        return {"jeu": gid, "niveau": k, "arret": "niveau non atteint"}
    sc0 = _resync(env, None, utilise_canevas(texte))
    coups = [(pf.NOMS[a], None, None) for a in fr.available_actions if a != 6 and a in pf.NOMS]
    if 6 in fr.available_actions:
        coups += [("CLICK", c[1], c[2]) for c in pf.clics(fr.frame[-1])]
    t0 = time.process_time()
    plan, inf = portefeuille(texte, sc0, None, coups, sec)
    r = {"jeu": gid, "niveau": k, "plan": None if plan is None else len(plan), "gagnant": inf.get("gagnant"),
         "cpu": round(time.process_time() - t0, 1)}
    if plan:
        inv = {v: c for c, v in pf.NOMS.items()}
        env2, _ = pf.env_au_niveau(gid, k)
        fin = None
        for a in plan:
            fin = pf.jouer(env2, (6, a[1], a[2]) if a[0] == "CLICK" else (inv[a[0]], None, None))
            if fin.levels_completed >= k or fin.state.name in ("WIN", "GAME_OVER"):
                break
        r["gagne"] = bool(fin is not None and (fin.levels_completed >= k or fin.state.name == "WIN"))
    return r


if __name__ == "__main__":
    _init()
    sec = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    for t in sys.argv[1].split(","):
        g, k = t.split(":")
        print(json.dumps(un(g, int(k), sec)), flush=True)
