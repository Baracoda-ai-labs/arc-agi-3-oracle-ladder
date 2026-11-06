"""[G] CW-375 : l'algorithme de `macro_g` (gel 2 : macros = largeur aux flèches, nouveauté sur les positions des pièces
de la classe pilotée ; recherche haute en largeur sur macros + actions non fléchées, alternance, repli sans alternance)
sur la THÉORIE CORRIGÉE d'Astra (`astra_ka59/.../ka59_n4_observe.pkl`, API `TheorieObservee.pas(etat, action)`, état
compact (croix, A, B, sélection, passager)). Actions abstraites du modèle : 0..3 flèches, 4/5 sélection de A/B.
Comparé à budget égal à l'A* pondéré d'Astra (`ModeleObserve.solve`). Plan → actions concrètes (`concrete`) → vrai jeu.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/macro_g_astra_ka59.py [secondes=30]"""
import json
import os
import pickle
import sys
import time
from collections import deque
from pathlib import Path

R = Path(__file__).resolve().parents[2]
L = R / "experiments/defi_llm/astra_ka59/livraison_ka59"
sys.path.insert(0, str(L / "ajouts"))


def macro_g(m, sec, alterner=True, depart=None, fini=None):
    """fini(s) : but (défaut : h == 0 du modèle) ; depart : état de départ (défaut : m.start)."""
    t0 = time.process_time()
    fini = fini or (lambda s: m.h(s) == 0)
    depart = m.start if depart is None else depart
    pil = (1, 2)  # pièces de la classe pilotée (14 et son jumeau) : la croix 11 n'en est pas

    def cle_macro(s):
        return tuple(s[i] for i in pil)

    def macros(s):
        vus, file, out = {cle_macro(s)}, deque([(s, [])]), []
        while file:
            u, ch = file.popleft()
            for a in range(4):
                v = m.step(u, a)
                if fini(v):
                    return [(v, [*ch, a], True)]
                k = cle_macro(v)
                if k in vus:
                    continue
                vus.add(k)
                out.append((v, [*ch, a], False))
                file.append((v, [*ch, a]))
        return out
    haut, file, plan = {depart}, deque([(depart, [], False)]), None
    while file and time.process_time() - t0 < sec and plan is None:
        s, ch, apres = file.popleft()
        suiv = [] if (apres and alterner) else [(v, cs, g, True) for v, cs, g in macros(s)]
        for a in (4, 5):
            v = m.step(s, a)
            if v != s:
                suiv.append((v, [a], fini(v), False))
        for v, cs, gagne, est_macro in suiv:
            if gagne:
                plan = [*ch, *cs]
                break
            if v in haut:
                continue
            haut.add(v)
            file.append((v, [*ch, *cs], est_macro))
    r = {"fin": None if plan is None else _rejouer(m, depart, plan), "plan": plan, "long": None if plan is None else len(plan), "etats_hauts": len(haut),
         "cpu": round(time.process_time() - t0, 2), "alterner": alterner}
    if plan is None and not file and alterner:
        return macro_g(m, sec - (time.process_time() - t0), False, depart, fini) | {"repli": True}
    return r


def _rejouer(m, s, plan):
    for a in plan:
        s = m.step(s, a)
    return s


def sous_buts(m, sec):
    """Cibles une à une, cumulées : croix ← pièce 0 ; deux cadres ← pièces 1 et 2 (appariement libre, comme h) ;
    ordres essayés, budget total sec. → (plan | None, journal)."""
    import itertools
    tar = m.G[1]

    def d(i, s, t):
        c = m.goals(s)[i]
        return abs(c[0] - t[0]) + abs(c[1] - t[1]) == 0
    cibles = {"croix": lambda s: d(0, s, tar[0]),
              "cadre1": lambda s: d(1, s, tar[1]) or d(2, s, tar[1]),
              "cadre2": lambda s: d(1, s, tar[2]) or d(2, s, tar[2])}
    t0, journal = time.process_time(), []
    for ordre in itertools.permutations(cibles):
        s, plan, faites = m.start, [], []
        for c in ordre:
            reste = sec - (time.process_time() - t0)
            if reste <= 0:
                break
            preds = [cibles[x] for x in (*faites, c)]
            r = macro_g(m, min(reste, sec / 3), depart=s, fini=lambda u, p=preds: all(f(u) for f in p))
            if r["plan"] is None:
                break
            s, plan, faites = r["fin"], plan + r["plan"], [*faites, c]
        journal.append({"ordre": ordre, "faites": len(faites), "coups": len(plan), "cpu": round(time.process_time() - t0, 1)})
        if len(faites) == 3 and m.h(s) == 0:
            return plan, journal
        if time.process_time() - t0 >= sec:
            break
    return None, journal


def main():
    sec = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    d = pickle.loads((L / "resultats/ka59_n4_observe.pkl").read_bytes())
    m = d["theorie"].modele
    out = {}
    out["macro_g"] = macro_g(m, sec)
    out["macro_g"].pop("fin", None)
    sb, journal = sous_buts(m, sec)
    out["sous_buts"] = {"long": None if sb is None else len(sb), "journal": journal}
    out["astar_astra"] = {k: v for k, v in m.solve(seconds=sec).items() if k != "actions"} | {}
    a = m.solve(seconds=sec).get("actions")
    out["astar_astra"]["long"] = None if a is None else len(a)
    plan = out["macro_g"]["plan"] or sb
    if plan:
        conc = m.concrete(plan)
        os.chdir(R)
        sys.path += [str(R / "experiments/T3.0"), str(R / "experiments/T3.1")]
        import plafonds as pf
        env, f0 = pf.env_au_niveau("ka59", 4)
        f, n = f0, 0
        for c in conc:
            f = pf.jouer(env, (c, None, None) if isinstance(c, int) else (6, c[2], c[1]))
            n += 1
            if f.levels_completed > f0.levels_completed or f.state.name in ("WIN", "GAME_OVER"):
                break
        out["rejeu_reel_macro_g"] = {"coups": n, "sur": len(conc), "etat": f.state.name,
                                     "franchi": f.levels_completed > f0.levels_completed or f.state.name == "WIN"}
    out["macro_g"]["plan"] = None if plan is None else "…"
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
