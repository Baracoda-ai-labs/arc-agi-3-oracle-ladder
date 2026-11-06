# SPDX-License-Identifier: MIT-0
"""CW-241 [session E] : le LANGAGE décrit-il des jeux écrits par des humains ? Juge au pixel près de l'interpréteur
PuzzleScript écrit dans le langage (`interpreteur_ps.json`, UN programme pour les 177 jeux) contre le vrai moteur du banc
(`experiments/banc_ps/`), même critère que `experiments/T3.7/juge_t4.py` (image + état des sprites visibles ; fins de niveau).
Les seules données propres au jeu sont celles de l'analyse `psmoteur.Jeu` (règles, couches, légende, victoire) et l'apparence
des objets (COULEURS, SPRITES) : section « niveau » du programme. Par niveau : 30 coups au hasard (graine fixe), puis la solution.
Usage : uv run python experiments/ps_langage/juge_ps.py <p000|p000,p003|tous|N premiers> [--hasard 30] [--temoin] [--details]
Sortie : une ligne par jeu et experiments/ps_langage/resultats/juge_<cible>.json."""
import ast
import json
import logging
import random
import re
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
ICI = Path(__file__).resolve().parent
ENV = R / "experiments/banc_ps/environment_files"
sys.path.insert(0, str(R / "experiments/T3.1"))
sys.path.insert(0, str(R / "experiments/banc_ps"))
sys.path.insert(0, str(R))
import mesure_exhaustivite as m  # noqa: E402
import psmoteur  # noqa: E402
from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine.enums import GameAction  # noqa: E402

TEMOIN = "--temoin" in sys.argv
PLAFOND_S = float(sys.argv[sys.argv.index("--plafond") + 1]) if "--plafond" in sys.argv else 900.0  # par jeu


INTERP = sys.argv[sys.argv.index("--interp") + 1] if "--interp" in sys.argv else "interpreteur_ps.json"


class TropLent(Exception):
    pass
NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE"}


def constantes_module(f):
    src = f.read_text()
    out = {}
    for nom in ("SOURCE_PS", "NIVEAUX_PS", "COULEURS", "SPRITES"):
        out[nom] = ast.literal_eval(re.search(rf"^{nom} = (.*)$", src, re.MULTILINE).group(1))
    return out


def _pixels(cols, spr, c):  # copie de runtime_ps._pixels (apparence d'un objet pour une case de c pixels)
    if spr is None:
        return [[cols[0]] * c for _ in range(c)]
    if c == 5:
        return [[cols[int(ch)] if ch != "." and int(ch) < len(cols) else -1 for ch in r] for r in spr]
    vus = [cols[int(ch)] for r in spr for ch in r if ch != "." and int(ch) < len(cols) and cols[int(ch)] >= 0]
    if not vus:
        return [[-1] * c for _ in range(c)]
    maj = max(set(vus), key=vus.count)
    return [[maj] * c for _ in range(c)]


def terme(t):
    return {"nom": t["nom"], "ens": sorted(t["ens"]), "neg": t["neg"], "mod": t["mod"]}


def regle(r):
    return {"g": [[[terme(t) for t in c] for c in p] for p in r["g"]],
            "d": [[[terme(t) for t in c] for c in p] for p in r["d"]], "dirs": r["dirs"], "cmds": r["cmds"],
            "texte": r["texte"]}


def donnees(f, source=None, niveaux=None):
    """Section « niveau » du programme : l'analyse psmoteur.Jeu du jeu (données) + apparence par niveau. `source` remplace
    le texte PuzzleScript (théorie candidate), `niveaux` la liste des niveaux PuzzleScript gardés (indices k)."""
    k = constantes_module(f)
    j = psmoteur.Jeu(source or k["SOURCE_PS"])
    groupes = lambda late: [[regle(r) for r in j.regles if r["groupe"] == g and r["late"] == late]
                            for g in sorted({r["groupe"] for r in j.regles if r["late"] == late})]
    etoile = {"rel": psmoteur.REL, "dirs": {d: list(v) for d, v in psmoteur.DIRS.items()}, "couche": j.couche, "fond": j.fond,
              "joueurs": sorted(j.joueurs), "noms": sorted(j.objets),
              "vict": [[q, sorted(x), sorted(y) if y is not None else None] for q, x, y in j.victoire],
              "gtot": groupes(False), "gtard": groupes(True), "rpm": "require_player_movement" in j.prelude}
    niv = {}
    for i, kp in enumerate(niveaux if niveaux is not None else k["NIVEAUX_PS"]):
        w, h = j.niveaux[kp]["w"], j.niveaux[kp]["h"]
        c = max(1, min(5, 64 // max(w, h)))
        niv[str(i)] = {"w": w, "h": h, "mod": {o: {"nom": o, "pixels": _pixels(k["COULEURS"][o], k["SPRITES"][o], c),
                                                  "couche": j.couche[o], "tags": ["type:" + o, "couche:%d" % j.couche[o]]}
                                              for o in j.objets}}
    return {**niv, "*": etoile}


COMPILE = "--compile" in sys.argv  # CW-256 : programme passé par le simulateur compilé de A (sim_rapide.ProgrammeCompile)


def programme(f):
    from chrysalide.arc3.langage import Programme
    if COMPILE:
        from chrysalide.arc3.sim_rapide import ProgrammeCompile as Programme
    if TEMOIN:
        prog = Programme({"regles": []})
    else:
        texte = json.loads((ICI / INTERP).read_text())
        texte["niveau"] = donnees(f)
        prog = Programme(texte)
    step = lambda scene, action: prog.step(scene, action)
    step.prog = prog
    return step


def au_niveau(arc, gid, verite, k):
    env = arc.make(gid)
    env.reset()
    for j in range(k):
        for a in verite["niveaux"][j]["solution"]:
            env.step(GameAction.from_id(a))
    assert env._game._current_level_index == k, f"préfixe faux au niveau {k}"
    return env


def jouer(env, step, coups, r, k):
    g = env._game
    scene = m._resync(env, None)
    cache = m._etat_cache(g)
    for i in coups:
        if time.time() - r["t0"] > PLAFOND_S:
            raise TropLent
        act = (NOMS[i], None, None)
        obs = env.step(GameAction.from_id(i))
        etat = obs.state.name if obs is not None else "?"
        change = g._current_level_index != k or etat == "WIN"
        _, image = m.scene_moteur(env)
        sprites, cache2 = m.etat_moteur(env)
        vrai = {"image": image, "complet": image, "sprites": sprites, "cache": cache2, "cache_change": cache2 != cache}
        cache = cache2
        scene.issue = None
        t0 = time.time()
        _, ok, err, npx, _ = m.juger(scene, step, act, vrai, False)
        r["secondes_coups"].append(round(time.time() - t0, 3))
        refus = getattr(step, "prog", None) and step.prog.etat.pop("refus", None)
        if refus:
            r["refus"] = refus
        decl = scene.issue in ("niveau", "victoire")
        if err:
            r["erreurs"] += 1
            r["details"].append((k, "erreur", act[0], err))
        if change:
            r["fins_reelles"] += 1
            r["fins_justes"] += decl
            if not decl:
                r["details"].append((k, "fin manquée", act[0]))
            return
        if decl:
            r["a_tort"] += 1
            r["details"].append((k, "fin à tort", act[0]))
        r["coups"] += 1
        r["exacts"] += ok
        if not ok:
            r["details"].append((k, "faux", act[0], npx))
            scene = m._resync(env, scene)


def juger_jeu(arc, d, n_hasard):
    gid = json.loads(next(d.glob("*/metadata.json")).read_text())["game_id"]
    verite = json.loads(next(d.glob("*/verite.json")).read_text())
    step = programme(next(d.glob(f"*/{d.name}.py")))
    r = {"jeu": d.name, "titre": verite.get("titre"), "coups": 0, "exacts": 0, "fins_reelles": 0, "fins_justes": 0, "a_tort": 0,
         "erreurs": 0, "details": [], "secondes_coups": [], "t0": time.time(), "trop_lent": False}
    for k, niv in enumerate(verite["niveaux"]):
      try:
        rng = random.Random(1000 + k)
        env = au_niveau(arc, gid, verite, k)
        offertes = [int(getattr(a, "value", a)) for a in env._game._available_actions]
        jouer(env, step, [rng.choice(offertes) for _ in range(n_hasard)], r, k)
        jouer(au_niveau(arc, gid, verite, k), step, niv["solution"], r, k)
      except TropLent:
        r["trop_lent"], r["niveaux_vus"] = True, k
        break
    r.pop("t0")
    s = sorted(r.pop("secondes_coups"))
    r["s_total"], r["s_p95"] = round(sum(s), 1), (s[int(0.95 * (len(s) - 1))] if s else None)
    return r


def main(args):
    logging.disable(logging.CRITICAL)
    cible = args[0]
    n_hasard = int(args[args.index("--hasard") + 1]) if "--hasard" in args else 30
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ENV))
    dossiers = sorted(d for d in ENV.iterdir() if d.is_dir())
    if cible.isdigit():
        dossiers = dossiers[:int(cible)]
    elif cible != "tous":
        dossiers = [d for d in dossiers if d.name in cible.split(",")]
    out = []
    for d in dossiers:
        t0 = time.time()
        try:
            r = juger_jeu(arc, d, n_hasard)
        except Exception as ex:  # noqa: BLE001 — échec compté
            r = {"jeu": d.name, "erreur_juge": f"{type(ex).__name__}: {str(ex)[:200]}"}
        r["s_jeu"] = round(time.time() - t0, 1)
        out.append(r)
        print(r["jeu"], f"exacts {r.get('exacts')}/{r.get('coups')}", f"fins {r.get('fins_justes')}/{r.get('fins_reelles')}",
              f"à_tort {r.get('a_tort')} erreurs {r.get('erreurs')}", f"{r['s_jeu']} s p95 {r.get('s_p95')}",
              r.get("erreur_juge", ""), "TROP LENT" if r.get("trop_lent") else "", r.get("refus", ""), r.get("details", [])[:3] if "--details" in args else "", flush=True)
    sortie = ICI / "resultats" / f"juge_{cible.replace(',', '_')}{'_temoin' if TEMOIN else ''}{'_' + Path(INTERP).stem if '--interp' in sys.argv else ''}{'_compile' if COMPILE else ''}.json"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
