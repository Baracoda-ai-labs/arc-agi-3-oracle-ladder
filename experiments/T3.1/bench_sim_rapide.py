"""T3.x : banc du simulateur compilé (`chrysalide/arc3/sim_rapide.py`) contre l'interpréteur (`langage.py`).
1. `--extraire [jeux…]` (moteur requis, donc le .venv avec arc_agi) : rejoue les parties R0 comme `mesure_exhaustivite.py`
   et enregistre, par jeu, les SEGMENTS (scène de départ lue dans le moteur + coups appliqués aux règles jusqu'au prochain
   départ : RESET, changement de niveau, fin de partie) dans `traces_sim.json.gz`. Aucun jeu témoin.
2. sans option : mesure états/s par jeu. Un état = copie de (scène, état caché) comme dans une recherche en largeur, puis un
   coup ; « avec rendu » ajoute l'image 64×64. Interprété = `Programme` + `copy.deepcopy` + `Scene.image` ; compilé =
   `ProgrammeCompile` + `cloner` + `image`. Vérifie au passage l'égalité bit à bit des images. → `bench_sim_rapide.json`.
Usage : uv run python experiments/T3.1/bench_sim_rapide.py [jeux…]"""
import copy
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

from chrysalide.arc3.langage import Programme, utilise_canevas
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner, image, image_complete

TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
TRACES = ICI / "traces_sim.json.gz"
CLES = ("nom", "tags", "x", "y", "couche", "visible", "bloquant", "echelle", "blocage", "cache")


def racine_donnees():
    """Les parties R0 et les fichiers de jeux ne sont pas dans une copie de travail : on remonte jusqu'à les trouver."""
    for d in (RACINE, *RACINE.parents):
        if (d / "runs_pod/R0").is_dir() and (d / "experiments/arc3/environment_files").is_dir():
            return d
    raise FileNotFoundError("runs_pod/R0 introuvable")


# ------------------------------------------------------------------ traces
def _np_json(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(type(o).__name__)


def scene_vers_json(s):
    """Scène de départ (v0.3 : données de niveau, catalogue de formes, nombre de niveaux, champs cachés des sprites)."""
    return {"vue": list(s.vue), "fond": s.fond, "letterbox": s.letterbox, "camera": list(s.camera), "niveau": s.niveau,
            "donnees": getattr(s, "donnees", {}), "modeles": getattr(s, "modeles", {}),
            "n_niveaux": getattr(s, "n_niveaux", None),
            "sprites": [{**{k: o[k] for k in CLES if k in o}, "pixels": np.asarray(o["pixels"]).tolist()} for o in s.sprites],
            "canevas": [{**c, "pixels": np.asarray(c["pixels"]).tolist()} for c in getattr(s, "canevas", [])]}


def scene_de_json(d):
    s = Scene(tuple(d["vue"]), d["fond"], d["letterbox"], d["sprites"], tuple(d["camera"]), donnees=d.get("donnees"),
              modeles={k: np.asarray(v) for k, v in (d.get("modeles") or {}).items()}, n_niveaux=d.get("n_niveaux"),
              niveau=d["niveau"], canevas=d.get("canevas"))
    s.niveau = d["niveau"]
    return s


def extraire(jeux):
    sys.path.insert(0, str(ICI))
    sys.path.insert(0, str(RACINE / "experiments/T2.12"))
    from arc_agi import Arcade, OperationMode
    from arcengine.enums import GameAction
    from fidelite import NUM, evenements
    from mesure_exhaustivite import _resync, action_de
    d = racine_donnees()
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(d / "experiments/arc3/environment_files"))
    traces = json.loads(gzip.decompress(TRACES.read_bytes())) if TRACES.exists() else {}
    for f in sorted((d / "runs_pod/R0").glob("*/artifacts/*_events.jsonl")):
        jeu = f.name[:4]
        if jeu in TEMOINS or not (ICI / "regles" / f"{jeu}.json").exists() or (jeux and jeu not in jeux):
            continue
        env = arc.make(f.name.split("_p")[0])
        env.reset()
        cv = utilise_canevas(regles(jeu))  # programme à canevas : la scène garde les canevas lus dans le moteur
        segs = [{"scene": scene_vers_json(_resync(env, None, cv)), "coups": []}]
        niveau = env._game._current_level_index
        for e in evenements(f):
            nom = e.get("action_name", "")
            if "board" not in e or e.get("type") == "initial" or nom not in NUM:
                continue
            a = action_de(e)
            g = GameAction.from_id(NUM[nom])
            env.step(g, data={"x": a[2], "y": a[1]}) if NUM[nom] == 6 else env.step(g)
            if a[0] == "RESET" or env._game._current_level_index != niveau or str(e.get("game_over")) == "True":
                segs.append({"scene": scene_vers_json(_resync(env, None, cv)), "coups": []})
                niveau = env._game._current_level_index
                continue
            segs[-1]["coups"].append(list(a))
        traces[jeu] = segs
        print(jeu, len(segs), "segments", sum(len(s["coups"]) for s in segs), "coups", flush=True)
    TRACES.write_bytes(gzip.compress(json.dumps(traces, default=_np_json).encode()))


def charger_traces():
    return json.loads(gzip.decompress(TRACES.read_bytes()))


def regles(jeu):
    return json.loads((ICI / "regles" / f"{jeu}.json").read_text())  # un texte par programme : les littéraux sont mutables


# ------------------------------------------------------------------ rejeu
def rejouer(jeu, segs, compile_, rendu, copie, garder=False):
    """Rejoue toutes les coups ; rend (secondes, nombre de coups, images si `garder`). Une erreur de règle = coup sans
    effet supplémentaire (comme le banc d'exhaustivité, qui la compte fausse)."""
    prog = (ProgrammeCompile if compile_ else Programme)(regles(jeu))
    scenes = [scene_de_json(s["scene"]) for s in segs]
    imgs, n, t = [], 0, 0.0
    for sc, seg in zip(scenes, segs, strict=True):
        t0 = time.perf_counter()
        for a in seg["coups"]:
            a = tuple(a)
            if copie:
                if compile_:
                    sc, prog.etat = cloner(sc, prog.etat)
                else:
                    sc, prog.etat = copy.deepcopy((sc, prog.etat))
            try:
                prog.step(sc, a)
            except Exception as x:  # noqa: BLE001
                if garder:
                    imgs.append(type(x).__name__)
            else:
                if rendu:
                    if sc.canevas:  # image complète (interface comprise) quand la scène a des canevas
                        im = image_complete(sc) if compile_ else sc.image_complete()
                    else:
                        im = image(sc) if compile_ else sc.image()
                    if garder:
                        imgs.append(im)
            n += 1
        t += time.perf_counter() - t0
    return t, n, imgs


def egales(i1, i2):
    return len(i1) == len(i2) and all(
        (isinstance(a, str) and a == b) or (not isinstance(a, str) and not isinstance(b, str) and np.array_equal(a, b))
        for a, b in zip(i1, i2, strict=True))


def main(jeux):
    traces = charger_traces()
    res = {}
    for jeu in sorted(traces):
        if jeux and jeu not in jeux:
            continue
        segs = traces[jeu]
        _, n, ii = rejouer(jeu, segs, False, True, False, garder=True)
        _, _, ic = rejouer(jeu, segs, True, True, True, garder=True)
        r = {"coups": n, "images_identiques": egales(ii, ic)}
        for nom, comp, rendu, copie in (("interp_nu", 0, 0, 0), ("interp", 0, 0, 1), ("interp_rendu", 0, 1, 1),
                                        ("comp_nu", 1, 0, 0), ("comp", 1, 0, 1), ("comp_rendu", 1, 1, 1),
                                        ("rendu_seul_interp", None, 1, 0), ("rendu_seul_comp", None, 1, 0)):
            if comp is None:
                sc = [scene_de_json(s["scene"]) for s in segs]
                f = image if nom.endswith("comp") else Scene.image
                t0 = time.perf_counter()
                for _ in range(20):
                    for s in sc:
                        f(s)
                r[nom] = round(20 * len(sc) / (time.perf_counter() - t0))
                continue
            rep, t, m = 0, 0.0, 0
            while t < 1.0:  # répété jusqu'à au moins 1 s de mesure
                dt, k, _ = rejouer(jeu, segs, comp, rendu, copie)
                t, m, rep = t + dt, m + k, rep + 1
            r[nom] = round(m / t)
        r["gain"] = round(r["comp"] / r["interp"], 1)
        r["gain_rendu"] = round(r["comp_rendu"] / r["interp_rendu"], 1)
        res[jeu] = r
        print(jeu, json.dumps(r), flush=True)
    (ICI / "bench_sim_rapide.json").write_text(json.dumps(res, indent=1))
    print("| jeu | coups | interp | interp+rendu | compilé | compilé+rendu | gain | gain rendu | identiques |")
    for jeu, r in res.items():
        print(f"| {jeu} | {r['coups']} | {r['interp']} | {r['interp_rendu']} | {r['comp']} | {r['comp_rendu']} | "
              f"×{r['gain']} | ×{r['gain_rendu']} | {r['images_identiques']} |")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--extraire"]:
        extraire(sys.argv[2:])
    else:
        main(sys.argv[1:])
