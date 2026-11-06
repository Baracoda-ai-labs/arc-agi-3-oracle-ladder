"""[G] CW-467.4 (b) : TEST DE MUTATION ENTRE BRANCHES du vérificateur. Pour un état s et une action A : successeur
s1 = pas(s, A) ; puis exploration d'AUTRES branches (marches aléatoires depuis s et depuis s1) ; puis s2 = pas(s, A).
Exigé : s2 == s1, et s inchangé (comparaison par copie profonde gelée avant). Deux niveaux :
  théorie  : `Theorie.pas(monde, action, taille)` (g50t déf. 2, théorie avec mémoire : fantôme, retour) ;
  programme : programme exporté, `ProgrammeCompile.step` sur `cloner(scene, etat)` (g50t, ka59 N4, re86 N5).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/mutation_branches.py → lignes JSON"""
import copy
import json
import os
import pickle
import random
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def gel(x):
    """Valeur comparable, indépendante des identités (sprites : dict → tuple trié ; tableaux → bytes)."""
    import numpy as np
    if isinstance(x, dict):
        return tuple(sorted((k, gel(v)) for k, v in x.items()))
    if isinstance(x, (list, tuple)):
        return tuple(gel(v) for v in x)
    if isinstance(x, (set, frozenset)):
        return frozenset(gel(v) for v in x)
    if isinstance(x, np.ndarray):
        return (x.shape, x.tobytes())
    if hasattr(x, "__dict__") and not isinstance(x, type):
        return (type(x).__name__, gel(vars(x)))
    return x


def theorie_g50t(n=200, profondeur=6):
    for f in ("CHRYS_RETOUR", "CHRYS_FANTOME", "CHRYS_POURSUITE_UTILE", "CHRYS_TENUE", "CHRYS_TRAITS_FINS", "CHRYS_BUT_CENTRE"):
        os.environ[f] = "1"
    os.environ["CHRYS_AMODAL"] = "2"
    d = pickle.loads((R / "experiments/T3.0/g50t_def2/theorie_victoire.pkl").read_bytes())
    th, s0, taille = d["th2"], d["tr2_0"], d["taille"]
    acts = [1, 2, 3, 4, 5]
    rng, ko, essais, etats = random.Random(0), [], 0, [s0]
    for _ in range(n):
        s = rng.choice(etats)
        avant = gel(copy.deepcopy(s))
        a = rng.choice(acts)
        s1 = th.pas(s, a, taille)[0]
        g1 = gel(s1)
        for _b in range(3):  # autres branches, depuis s et depuis s1
            x = rng.choice([s, s1])
            for _p in range(profondeur):
                x = th.pas(x, rng.choice(acts), taille)[0]
        s2 = th.pas(s, a, taille)[0]
        essais += 1
        if gel(s2) != g1 or gel(s) != avant:
            ko.append({"action": a, "successeur_change": gel(s2) != g1, "etat_modifie": gel(s) != avant})
        etats.append(s1)
    return {"niveau": "théorie", "cas": "g50t N1 (fantôme, retour)", "essais": essais, "echecs": len(ko), "exemples": ko[:3]}


def programme(nom, prog, scene, etat, acts, n=200, profondeur=6):
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    p = ProgrammeCompile(prog)
    e0 = p.etat if etat is None else etat

    def pas(sc, e, a):
        s2, e2 = cloner(sc, e)
        p.etat = e2
        try:
            p.step(s2, a)
        except Exception:  # noqa: BLE001 — coup qui plante : ignoré (même traitement que la recherche)
            return None
        return s2, p.etat
    rng, ko, essais, etats = random.Random(0), [], 0, [(scene, e0)]
    for _ in range(n):
        s, e = rng.choice(etats)
        avant = (gel(s.sprites), gel(e))
        a = rng.choice(acts)
        r1 = pas(s, e, a)
        if r1 is None:
            continue
        g1 = (gel(r1[0].sprites), gel(r1[1]), r1[0].issue)
        for _b in range(3):
            x = rng.choice([(s, e), r1])
            for _p in range(profondeur):
                y = pas(*x, rng.choice(acts))
                if y is None or y[0].issue is not None:
                    break
                x = y
        r2 = pas(s, e, a)
        essais += 1
        if r2 is None or (gel(r2[0].sprites), gel(r2[1]), r2[0].issue) != g1 or (gel(s.sprites), gel(e)) != avant:
            ko.append({"action": str(a), "successeur_change": r2 is None or (gel(r2[0].sprites), gel(r2[1]), r2[0].issue) != g1,
                       "etat_modifie": (gel(s.sprites), gel(e)) != avant})
        if r1[0].issue is None:
            etats.append(r1)
    return {"niveau": "programme", "cas": nom, "essais": essais, "echecs": len(ko), "exemples": ko[:3]}


def main():
    print(json.dumps(theorie_g50t(), ensure_ascii=False, default=str), flush=True)
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    d = pickle.loads((R / "experiments/T3.0/g50t_def2/theorie_victoire.pkl").read_bytes())
    th = d["th2"]
    th.but = ("centre", 281, 9)
    prog, _ = exporter(th, d["taille"])
    sc = Scene((d["taille"][1], d["taille"][0]), d["fond"], d["fond"], [_sprite(o) for o in d["tr2_0"]])
    fl = [(a, None, None) for a in ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")]
    print(json.dumps(programme("g50t N1", prog, sc, None, fl), ensure_ascii=False, default=str), flush=True)
    for cas in ("ka59_n4_creux", "re86_n5_peint"):
        D = pickle.loads((R / f"experiments/T3.0/dossiers_g/{cas}.pkl").read_bytes())
        os.environ.update(D["drapeaux"])
        t = D["theorie"]
        t.but = D["buts"][0]
        pg, _ = exporter(t, D["taille"])
        s = Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])
        acts = [(a, None, None) for a in ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")]
        if cas.startswith("ka59"):
            acts += [("CLICK", 32, 30), ("CLICK", 29, 21), ("CLICK", 47, 29)]
        print(json.dumps(programme(cas, pg, s, None, acts), ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(R))
    main()
