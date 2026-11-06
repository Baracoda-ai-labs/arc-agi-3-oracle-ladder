# SPDX-License-Identifier: MIT-0
"""CW-203 [session B] : le LANGAGE décrit-il chaque mécanique des jeux T4 ? Juge au pixel près, comme le banc des 20 jeux
publics (`mesure_exhaustivite.juger` : image + état des sprites visibles), d'un programme de FAMILLE
(`experiments/T3.7/regles/<famille>.json`, un seul programme pour tous les jeux de la famille) contre le vrai moteur.
Par jeu et par niveau k : (a) 30 coups au hasard depuis le début du niveau (graine fixe ; arrêt à la fin du niveau ou à la
défaite), puis (b) la solution de `verite.json`. Fin de niveau : déclarée par le programme (`scene.issue`) contre le moteur.
Usage : uv run python experiments/T3.7/juge_t4.py <environment_files T4> <jeu|famille|tous> [--hasard 30] [--details] [--temoin]
Coups exacts = coups NON terminaux (ni fin de niveau ni défaite) ; les coups terminaux sont jugés par fins / défaites.
Sortie : une ligne par jeu (coups exacts / coups, fins justes / réelles, à tort, erreurs) et experiments/T3.7/juge_<cible>.json."""
import json
import logging
import random
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "experiments/T3.1"))
sys.path.insert(0, str(R))
import mesure_exhaustivite as m
from arc_agi import Arcade, OperationMode
from arcengine.enums import GameAction

TEMOIN = "--temoin" in sys.argv  # témoin « aucune règle » (le banc est-il à vide ?)
NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE"}


def constantes(module):
    """Palette du jeu NON VISIBLE au début d'un niveau (couleur allumée de l'interrupteur, compteur plein, couleurs et formes
    de l'icône d'attribut) : lue dans CONFIG / GABARITS du module, injectée en section `niveau` "*" (paramètres du jeu)."""
    import ast
    import re
    src = module.read_text()
    conf = ast.literal_eval(re.search(r"^CONFIG = (.*)$", src, re.MULTILINE).group(1))
    gab = ast.literal_eval(re.search(r"^GABARITS = (.*)$", src, re.MULTILINE).group(1))
    c = conf["couleurs"]
    formes = [gab[f"forme{i}"]["pixels"] for i in range(10) if f"forme{i}" in gab]
    return {"inter_on": c["inter_on"], "inter_off": c["inter_off"], "pip_plein": c["pip_plein"], "pip_vide": c["pip_vide"],
            "attr": c["attr"], "formes": formes,
            "couleur_formes": [next(v for r in f for v in r if v >= 0) for f in formes]}


def programme(famille, consts=None):
    from chrysalide.arc3.langage import Programme
    if TEMOIN:
        prog = Programme({"regles": []})
        return lambda scene, action: prog.step(scene, action)
    import os
    chemin = os.environ.get(f"REGLES_{famille.upper()}") or R / f"experiments/T3.7/regles/{famille}.json"  # ablations
    texte = json.loads(Path(chemin).read_text())
    if consts:
        texte.setdefault("niveau", {})["*"] = consts
    prog = Programme(texte)
    return lambda scene, action: prog.step(scene, action)


def coup(a, niv):
    """Coup de verite.json (ou tiré au hasard) → (id moteur, data, action du langage)."""
    if isinstance(a, int):
        return a, None, (NOMS[a], None, None)
    s, (ox, oy) = niv["case_px"], niv["origine_px"]
    cases = [e["case"] for e in niv["elements"] if e.get("type") == "tuile" and e.get("case")]
    n, mm = max(c[0] for c in cases) + 1, max(c[1] for c in cases) + 1
    cx, cy = {"t": (a[1] % n, a[1] // n), "r": (n, a[1]), "c": (a[1], mm)}[a[0]]
    x, y = ox + cx * s + s // 2, oy + cy * s + s // 2
    return 6, {"x": int(x), "y": int(y)}, ("CLICK", int(y), int(x))


def hasard(niv, famille, rng, offertes=(1, 2, 3, 4)):
    if famille == "dedale":
        return rng.choice([a for a in offertes if a in NOMS])
    # tuiles : clic au hasard dans la bande des tuiles et des boutons (y compris des cases vides : « rien »)
    s, (ox, oy) = niv["case_px"], niv["origine_px"]
    x, y = ox + rng.randrange(-s, 7 * s), oy + rng.randrange(-s, 7 * s)
    return 6, {"x": max(0, min(63, x)), "y": max(0, min(63, y))}, ("CLICK", max(0, min(63, y)), max(0, min(63, x)))


def au_niveau(arc, gid, verite, k):
    env = arc.make(gid)
    env.reset()
    for j in range(k):
        for a in verite["niveaux"][j]["solution"]:
            i, d, _ = coup(a, verite["niveaux"][j])
            env.step(GameAction.from_id(i), data=d) if d else env.step(GameAction.from_id(i))
    assert env._game._current_level_index == k, f"préfixe faux au niveau {k}"
    return env


def jouer(env, step, coups, r, k):
    g = env._game
    scene = m._resync(env, None)
    cache = m._etat_cache(g)
    for i, d, act in coups:
        obs = env.step(GameAction.from_id(i), data=d) if d else env.step(GameAction.from_id(i))
        etat = obs.state.name if obs is not None else "?"
        change = g._current_level_index != k or etat == "WIN"
        perdu = etat == "GAME_OVER"
        _, image = m.scene_moteur(env)
        sprites, cache2 = m.etat_moteur(env)
        vrai = {"image": image, "complet": image, "sprites": sprites, "cache": cache2, "cache_change": cache2 != cache}
        cache = cache2
        scene.issue = None
        _, ok, err, npx, _ = m.juger(scene, step, act, vrai, False)
        decl = scene.issue in ("niveau", "victoire")
        perdu_decl = scene.issue == "defaite"
        if err:
            r["erreurs"] += 1
            r["details"].append((k, "erreur", act, err))
        if change:
            r["fins_reelles"] += 1
            r["fins_justes"] += decl
            if not decl:
                r["details"].append((k, "fin manquée", act))
            return
        if decl:
            r["a_tort"] += 1
            r["details"].append((k, "fin à tort", act))
        if perdu:
            r["defaites"] += 1
            r["defaites_justes"] += perdu_decl
            return
        r["coups"] += 1
        r["exacts"] += ok
        if not ok:
            r["details"].append((k, "faux", act, npx))
            scene = m._resync(env, scene)


def juger_jeu(arc, gid, env_dir, famille, n_hasard=30):
    verite = json.loads(next((env_dir / gid[:4]).glob("*/verite.json")).read_text())
    step = programme(famille, constantes(next((env_dir / gid[:4]).glob(f"*/{gid[:4]}.py"))))
    r = {"jeu": gid[:4], "famille": famille, "mecaniques": verite["mecaniques"], "coups": 0, "exacts": 0, "fins_reelles": 0,
         "fins_justes": 0, "a_tort": 0, "defaites": 0, "defaites_justes": 0, "erreurs": 0, "details": []}
    for k, niv in enumerate(verite["niveaux"]):
        rng = random.Random(1000 + k)
        env = au_niveau(arc, gid, verite, k)
        offertes = [int(getattr(a, "value", a)) for a in env._game._available_actions]
        jouer(env, step, [hasard(niv, famille, rng) if famille == "tuiles"
                          else coup(hasard(niv, famille, rng, offertes), niv) for _ in range(n_hasard)], r, k)
        jouer(au_niveau(arc, gid, verite, k), step, [coup(a, niv) for a in niv["solution"]], r, k)
    return r


def main(args):
    logging.disable(logging.CRITICAL)
    env_dir, cible = Path(args[0]), args[1]
    n_hasard = int(args[args.index("--hasard") + 1]) if "--hasard" in args else 30
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(env_dir))
    jeux = []
    for d in sorted(env_dir.iterdir()):
        meta = next(d.glob("*/metadata.json"), None)
        if meta is None:
            continue
        v = json.loads(next(d.glob("*/verite.json")).read_text())
        if cible in ("tous", v["famille"], d.name) or d.name in cible.split(","):
            jeux.append((json.loads(meta.read_text())["game_id"], v["famille"]))
    out = []
    for gid, fam in jeux:
        try:
            r = juger_jeu(arc, gid, env_dir, fam, n_hasard)
        except Exception as ex:  # noqa: BLE001 — échec compté
            r = {"jeu": gid[:4], "famille": fam, "erreur_juge": f"{type(ex).__name__}: {str(ex)[:150]}"}
        out.append(r)
        print(r["jeu"], fam, ",".join(r.get("mecaniques", [])), f"exacts {r.get('exacts')}/{r.get('coups')}",
              f"fins {r.get('fins_justes')}/{r.get('fins_reelles')} à_tort {r.get('a_tort')}",
              f"défaites {r.get('defaites_justes')}/{r.get('defaites')} erreurs {r.get('erreurs')}", r.get("erreur_juge", ""),
              r.get("details", [])[:4] if "--details" in args else "", flush=True)
    sortie = R / f"experiments/T3.7/juge_{cible.replace(',', '_')}{'_temoin' if TEMOIN else ''}.json"
    sortie.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    np.seterr(all="ignore")


if __name__ == "__main__":
    main(sys.argv[1:])
