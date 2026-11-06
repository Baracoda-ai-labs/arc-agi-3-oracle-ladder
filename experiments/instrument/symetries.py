# SPDX-License-Identifier: MIT-0
"""Symétries VÉRIFIÉES des programmes exacts (CW-256/271, A, usage « moins d'états »). Pour chaque jeu (niveau 1) et chaque
transformation T (miroir horizontal H, miroir vertical V, demi-tour R), on teste sur des états atteints au hasard :
  (1) image(step(T(s), T(a))) == T(image(step(s, a))) pour chaque action a (dynamique invariante) ;
  (2) distance_but(T(s)) == distance_but(s) (but invariant).
Une symétrie n'est déclarée que si TOUS les tests passent ; sinon le premier contre-exemple est noté. Si T tient, deux états
images l'un de l'autre peuvent être fusionnés dans la recherche (quotient). Usage : uv run python experiments/instrument/symetries.py"""
import copy
import json
import random
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
ACT = {"H": {"LEFT": "RIGHT", "RIGHT": "LEFT"}, "V": {"UP": "DOWN", "DOWN": "UP"},
       "R": {"LEFT": "RIGHT", "RIGHT": "LEFT", "UP": "DOWN", "DOWN": "UP"}}


def t_image(im, t):
    return {"H": np.fliplr, "V": np.flipud, "R": lambda a: np.flipud(np.fliplr(a))}[t](np.asarray(im))


def t_scene(sc, t):
    """Scène transformée (sans canevas ni caméra décalée : refusé en amont)."""
    from chrysalide.arc3.sim_rapide import cloner
    n, _ = cloner(sc, {})
    h, w = sc.vue
    for s in n.sprites:
        px = np.asarray(s["pixels"])
        ph, pw = px.shape[:2]
        if t in ("H", "R"):
            s["x"] = w - s["x"] - pw
        if t in ("V", "R"):
            s["y"] = h - s["y"] - ph
        s["pixels"] = t_image(px, t).copy()
    return n


def t_action(a, t, sc):
    if a[0] == "CLICK":
        h, w = sc.vue
        r, c = a[1], a[2]
        return ("CLICK", h - 1 - r if t in ("V", "R") else r, w - 1 - c if t in ("H", "R") else c)
    return (ACT[t].get(a[0], a[0]), None, None)


def tester(gid, n_etats=40, graine=0):
    import plafonds
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import Programme, utilise_canevas
    from chrysalide.arc3.logique.plan_langage import distance_but, regle_victoire
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    f = RACINE / "experiments/T3.1/regles" / f"{gid}.json"
    texte = json.loads(f.read_text())
    if utilise_canevas(texte):
        return {"refus": "canevas (non transformé dans cette v1)"}
    env, fr = plafonds.env_au_niveau(gid, 1)
    sc0 = _resync(env, None, False)
    if tuple(getattr(sc0, "camera", (0, 0)) or (0, 0)) != (0, 0):
        return {"refus": "caméra décalée"}
    prog, interp, regle = ProgrammeCompile(texte), Programme(texte), regle_victoire(texte)
    dispo = [a for a in fr.available_actions if a != 6 and a in plafonds.NOMS]
    coups = [(plafonds.NOMS[a], None, None) for a in dispo]
    if 6 in fr.available_actions:
        coups += [("CLICK", c[1], c[2]) for c in plafonds.clics(fr.frame[-1])]
    rnd = random.Random(graine)
    etats, (sc, e) = [], cloner(sc0, prog.etat)
    for _ in range(n_etats):  # marche au hasard dans le programme : états atteignables
        etats.append(cloner(sc, e))
        sc, e = cloner(sc, e)
        prog.etat = e
        prog.step(sc, rnd.choice(coups))
        e = prog.etat
        if sc.issue is not None:
            sc, e = cloner(sc0, prog.etat)
    out = {}
    # décor fixe = sprites qui n'ont pas bougé pendant la marche ; la fusion s ~ T(s) n'aide que si T(s0) est atteignable,
    # donc au minimum si le décor fixe est lui-même invariant par T
    from chrysalide.arc3.logique.plan_langage import _gel_sprite
    fixes = [i for i in range(len(sc0.sprites))
             if all(i < len(x.sprites) and _gel_sprite(x.sprites[i]) == _gel_sprite(sc0.sprites[i]) for x, _ in etats)]
    def decor(scene):
        return sorted(repr(_gel_sprite(scene.sprites[i])) for i in fixes)
    for t in ("H", "V", "R"):
        if decor(t_scene(sc0, t)) != decor(sc0):
            out[t] = "décor fixe non symétrique"
            continue
        verdict = "tient"
        for i, (s, e) in enumerate(etats):
            ts = t_scene(s, t)
            if regle is not None and distance_but(interp, regle, s, e) != distance_but(interp, regle, ts, e):
                verdict = f"but non invariant (état {i})"
                break
            for a in coups:
                s1, e1 = cloner(s, e)
                prog.etat = copy.deepcopy(e1)
                prog.step(s1, a)
                s2, e2 = cloner(ts, e)
                prog.etat = copy.deepcopy(e2)
                prog.step(s2, t_action(a, t, s))
                if not np.array_equal(t_image(s1.image(), t), np.asarray(s2.image())) or s1.issue != s2.issue:
                    verdict = f"dynamique non invariante (état {i}, action {a[0]})"
                    break
            if verdict != "tient":
                break
        out[t] = verdict
    return out


def main():
    jeux = sorted(p.stem for p in (RACINE / "experiments/T3.1/regles").glob("*.json") if "_" not in p.stem and p.stem not in TEMOINS)
    res = {}
    for g in jeux:
        try:
            res[g] = tester(g)
        except Exception as e:  # noqa: BLE001
            res[g] = {"erreur": f"{type(e).__name__}: {e}"[:120]}
        print(g, res[g], flush=True)
    (RACINE / "experiments/instrument/symetries.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
