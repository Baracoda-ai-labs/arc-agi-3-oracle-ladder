# SPDX-License-Identifier: MIT-0
"""CW-410 (B + G) : paires d'actions indépendantes, PRÉDITES par l'ontologie v1 (`chrysalide/langue/independance.py`)
et MESURÉES sur le programme exact de chaque jeu public (témoins exclus avant lecture).
Mesure : on rejoue la 1re trace R0 dans le vrai jeu ; à des états échantillonnés, on applique a·b et b·a au programme
exact (copies) et on compare scène (sprites, image) et variables. Une paire « commute » si les deux ordres donnent le
même état à TOUS les états échantillonnés où ni a ni b ne finit le niveau.
Contrôle de sûreté (bloquant pour G) : aucune paire prédite indépendante ne doit échouer à commuter.
Usage : uv run python experiments/meta_modele/independance_mesure.py [pas_max=60] [tous_les=4] → independance.json"""
import copy
import json
import sys
from itertools import combinations
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(R), str(R / "experiments/T3.1"), str(R / "experiments/T3.0"), str(R / "experiments/T2.12")]
TEM = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
FLECHES = ("UP", "DOWN", "LEFT", "RIGHT")

# Diagnostic (banc de B seulement) : lois de la mémoire globale → mécanismes de l'ontologie, par classe d'action.
LOI_VERS = {"flèches + blocage": {"fleche": ["deplacement", "blocage"]},
            "sélection par clic": {"clic": ["selection_clic"]},
            "état cyclique": {"clic": ["etat_cyclique"]},
            "sélection par cycle": {"space": ["selection_marqueur"]},
            "création d'objet": {"space": ["creation"]},
            "annulation UNDO": {"undo": ["annulation"]},
            "déclencheur → porte": {"fleche": ["bouton"]},
            "ramassage": {"fleche": ["ramassage"]},
            "téléportation": {"fleche": ["teleportation"]},
            "rotation 90°": {"fleche": ["transformation"]},
            "propagation aux voisins": {"clic": ["etat_cyclique"]},
            "modificateur au contact": {"fleche": ["transformation"]},
            "portage": {"fleche": ["poussee"]}, "poussée en chaîne": {"fleche": ["poussee"]},
            "glissade jusqu'à l'arrêt": {"fleche": ["glissement"]},
            "réglage puis lancement": {"space": ["lancement"]},
            "miroir": {"fleche": ["deplacement"]}}
TOUJOURS = {"autonomes": ["autonome"], "jauge de coups": ["economie"]}


def classe(a):
    return "fleche" if a[0] in FLECHES else {"SPACE": "space", "CLICK": "clic", "UNDO": "undo"}.get(a[0], a[0])


def theorie_diagnostic(jeu, lois):
    par_classe, toujours = {}, []
    for nom, loi in lois.items():
        if jeu not in loi["jeux"]:
            continue
        for c, ms in LOI_VERS.get(nom, {}).items():
            par_classe.setdefault(c, []).extend(ms)
        toujours += TOUJOURS.get(nom, [])
    return par_classe, toujours


def cle(p, sc):
    spr = repr([sorted((k, repr(v)) for k, v in o.items()) for o in sc.sprites])
    return spr + repr(sorted(p.etat.items(), key=str)) + repr(getattr(sc, "issue", None))


def mesurer(f, pas_max, tous_les):
    from arcengine.enums import GameAction
    from fidelite import NUM, evenements
    from mesure_exhaustivite import _resync, action_de, arcade

    from chrysalide.arc3.langage import Programme, utilise_canevas
    jeu = Path(f).name[:4]
    texte = json.loads((R / "experiments/T3.1/regles" / f"{jeu}.json").read_text())
    cv = utilise_canevas(texte)
    env = arcade().make(Path(f).name.split("_p")[0])
    env.reset()
    prog, sc = Programme(texte), _resync(env, None, cv)
    niv, etats, actions, t = env._game._current_level_index, [], set(), 0
    for e in evenements(f):
        if "board" not in e or e.get("type") == "initial" or e.get("action_name", "") not in NUM:
            continue
        a, nom = action_de(e), e["action_name"]
        if a[0] != "RESET":
            actions.add(a if a[0] == "CLICK" else (a[0], None, None))
        if t % tous_les == 0:
            etats.append(copy.deepcopy((prog, sc)))
        env.step(GameAction.from_id(NUM[nom]), data={"x": a[2], "y": a[1]}) if NUM[nom] == 6 else \
            env.step(GameAction.from_id(NUM[nom]))
        t += 1
        if a[0] != "RESET":
            prog.step(sc, a)
        if a[0] == "RESET" or env._game._current_level_index != niv or getattr(sc, "issue", None):
            prog, sc, niv = Programme(texte), _resync(env, None, cv), env._game._current_level_index
        if t >= pas_max:
            break
    clics = sorted(x for x in actions if x[0] == "CLICK")[:4]
    acts = sorted(x for x in actions if x[0] != "CLICK") + clics
    res = {}
    for a, b in combinations(acts, 2):
        n = ok = 0
        for st in etats:
            fins = []
            for u, v in ((a, b), (b, a)):
                p, s = copy.deepcopy(st)
                p.step(s, u)
                if getattr(s, "issue", None):
                    break
                p.step(s, v)
                fins.append(cle(p, s))
            if len(fins) == 2:
                n += 1
                ok += fins[0] == fins[1]
        res[f"{a[0]}{'' if a[1] is None else a[1:]}|{b[0]}{'' if b[1] is None else b[1:]}"] = \
            {"classes": [classe(a), classe(b)], "n": n, "commute": ok}
    return res, len(etats)


def main(a):
    from chrysalide.langue.independance import conditionnelle, independantes
    pas_max, tous_les = int(a[0]) if a else 60, int(a[1]) if len(a) > 1 else 4
    lois = json.loads((R / "docs/memoire_globale.json").read_text())["lois"]
    traces = {}
    for f in sorted((R / "runs_pod/R0").glob("*/artifacts/*_events.jsonl")):
        j = f.name[:4]
        if j not in TEM and j not in traces and (R / "experiments/T3.1/regles" / f"{j}.json").exists():
            traces[j] = f
    out, tot = {}, {"paires": 0, "mesurees": 0, "commutent": 0, "predites": 0, "faux_independants": 0, "manquees": 0,
           "conditionnelles": 0, "conditionnelles_commutent": 0}
    for j, f in traces.items():
        par_classe, toujours = theorie_diagnostic(j, lois)
        res, ne = mesurer(f, pas_max, tous_les)
        for r in res.values():
            ca, cb = r["classes"]
            r["predite"] = independantes(par_classe.get(ca, []), par_classe.get(cb, []), toujours)
            r["conditionnelle"] = conditionnelle(par_classe.get(ca, []), par_classe.get(cb, []), toujours) is not None
            r["mesuree"] = r["n"] > 0 and r["commute"] == r["n"]
            tot["paires"] += 1
            tot["mesurees"] += r["n"] > 0
            tot["commutent"] += r["mesuree"]
            tot["predites"] += r["predite"]
            tot["faux_independants"] += r["predite"] and r["n"] > 0 and not r["mesuree"]
            tot["manquees"] += r["mesuree"] and not r["predite"]
            tot["conditionnelles"] += r["conditionnelle"]
            tot["conditionnelles_commutent"] += r["conditionnelle"] and r["mesuree"]
        out[j] = {"etats": ne, "toujours": toujours, "paires": res}
        print(j, ne, sum(r["mesuree"] for r in res.values()), "/", len(res), "commutent ;",
              sum(r["predite"] for r in res.values()), "prédites", flush=True)
    (R / "experiments/meta_modele/independance.json").write_text(
        json.dumps({"total": tot, "jeux": out}, ensure_ascii=False, indent=1))
    print("TOTAL", tot)


if __name__ == "__main__":
    main(sys.argv[1:])
