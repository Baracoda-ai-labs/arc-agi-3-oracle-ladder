"""[G] V1-B (CW-351.4) hors g50t : pour un jeu, théorie de C induite sur la 1re vie de Franzen (trace de B, comme
`experiments/T3.0/divergences_traces.py`, induction 60 s), exportée dans le langage ; depuis le DÉBUT du niveau, trois
recherches sur CE programme, même budget : meilleur d'abord guidé par `h_relations` (V1-B), non guidé, `macro_g` (gel 2).
Aucun programme exact lu. Le but est celui de la théorie (aucun but → V1-B non applicable, compté).
Usage : drapeaux de C + PYTHONPATH=. .venv/bin/python experiments/G/banc_v1b.py <jeu> [secondes=300] → ligne JSON"""
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/G"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
os.chdir(RACINE)
import numpy as np
from guidage import h_relations, meilleur_dabord

from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import induire
from chrysalide.arc3.moteur import _codes_c, _sprite
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile

NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE"}


def niveaux_gagnes(gid):
    """Rejoue la trace de B ; par niveau gagné : grilles et lots de la vie gagnante (depuis le début du niveau ou la
    dernière mort), et le lot final (celui qui franchit le niveau). → ({niveau: dict(grilles, lots, finale)}, env, k_max)"""
    from divergences_traces import jouer
    from mesure_exhaustivite import arcade
    lignes = [json.loads(x) for x in Path(f"experiments/T3.10/diag_ref/traces/{gid}_ref/{gid}_trace.jsonl").read_text().splitlines()]
    env = arcade().make(gid)
    f = env.reset()
    out, grilles, gl, k = {}, [np.asarray(f.frame[-1])], [], 0
    for ln in lignes:
        if "lot" not in ln:
            continue
        for a in ln["lot"]["actions"]:
            f = jouer(env, a)
        if f.levels_completed > k:
            out[k + 1] = {"grilles": [g.tolist() for g in grilles], "lots": gl, "finale": ln["lot"]}
            k = f.levels_completed
            grilles, gl = [np.asarray(f.frame[-1])], []
        elif f.state.name != "NOT_FINISHED" or len(ln["lot"]["actions"]) != 1:
            grilles, gl = [np.asarray(f.frame[-1])], []  # mort, reset ou lot multiple : vie recommencée
            if f.state.name == "GAME_OVER":
                f = env.step(__import__("arcengine.enums", fromlist=["GameAction"]).GameAction.RESET)
                grilles = [np.asarray(f.frame[-1])]
        else:
            grilles.append(np.asarray(f.frame[-1]))
            gl.append(ln["lot"])
    return out, k


def main():
    gid, sec = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 300
    k = int(sys.argv[3]) if len(sys.argv) > 3 else None
    gagnes, kmax = niveaux_gagnes(gid)
    k = k or max(gagnes, default=kmax)  # niveau étudié (dernier gagné par Franzen) : théorie des niveaux gagnés AVANT lui (comme `theorie_precedente` du moteur)
    prec = [gagnes[i] for i in sorted(gagnes) if i < k]
    # comme `theorie_precedente` du moteur, mais clics compris (codes de C : `_codes_c`, ('clic', x, y))
    src = [(Trajectoire(q["grilles"], _codes_c(q["lots"])), None, _codes_c([q["finale"]])[0]) for q in prec
           if _codes_c(q["lots"]) is not None and _codes_c([q["finale"]]) is not None]
    th = induire(src, limite_s=60)[0] if src else None
    if th is None:
        print(json.dumps({"jeu": gid, "niveau": k, "erreur": "aucun niveau précédent exploitable"}), flush=True)
        return
    depart = gagnes[k]["grilles"][0] if k in gagnes else None
    tr = Trajectoire(prec[-1]["grilles"], [c for c in _codes_c(prec[-1]["lots"])])
    acts = [c for p in prec for c in (_codes_c(p["lots"]) or [])]
    ligne = {"jeu": gid, "niveau": k, "precedents": len(prec), "but": getattr(th, "but", None),
             "moves": len(th.moves), "solides": sorted(th.solides), "tenue_cases": len(getattr(th, "tenue_cases", ()))}
    prog, non = exporter(th, tr.taille)
    ligne["non_exportes"] = non
    h = h_relations(th)
    if depart is None:
        print(json.dumps({**ligne, "erreur": "niveau non gagné par Franzen : départ non reconstruit"}, default=str))
        return
    t0 = Trajectoire([depart], [])
    s = Scene((t0.taille[1], t0.taille[0]), t0.fond, t0.fond, [_sprite(o) for o in t0.etats[0]])
    ligne["h_depart"] = None if h is None else h(s)
    print(json.dumps(ligne, ensure_ascii=False, default=str), flush=True)
    if non or not ligne["but"]:
        return
    acts_jeu = sorted({a for a in acts if isinstance(a, int) and a in NOMS} | {1, 2, 3, 4})
    noms = [(NOMS[a], None, None) for a in acts_jeu]
    for nom, hh in (("V1-B", h), ("non guidé", lambda sc: 0)):
        if hh is None:
            continue
        p = ProgrammeCompile(prog)
        plan, inf = meilleur_dabord(prog, s, p.etat, noms, hh, 200000, sec)
        print(json.dumps({"jeu": gid, "recherche": nom, "plan": None if plan is None else len(plan), **inf}), flush=True)
    from banc_p0 import _init
    _init()
    import macro_g
    p = ProgrammeCompile(prog)
    r = macro_g.chercher(gid, k, 20000, sec, texte=prog, scene=s, etat=p.etat, actions=acts_jeu, verifier=False)
    print(json.dumps({"jeu": gid, "recherche": "macro_g", **{x: r.get(x) for x in ("arret", "plan", "etats_hauts", "cpu")}}),
          flush=True)


if __name__ == "__main__":
    main()
