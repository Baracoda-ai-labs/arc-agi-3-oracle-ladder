# SPDX-License-Identifier: MIT-0
"""Diagnostic à 4 configurations (CW-224.1, session A) sur la sélection figée (SELECTION.md), niveau 1, moteur seul.
État initial contrôlé : début du niveau 1 (RESET). Amorce identique pour tous : K coups au hasard (graine fixe) joués sur
une copie, qui servent à l'induction. Puis, depuis le début du niveau :
  A = règles induites (théorie de C sur l'amorce) + but inféré (but induit, sinon but supposé comme MoteurC) ;
  B = règles induites + but « exact » (but induit par C quand on lui montre aussi la démonstration gagnante de D) ;
  C = règles exactes (le VRAI jeu copié sert de simulateur, oracle de banc) + but inféré (buts candidats de A, dans l'ordre) ;
  D = règles exactes + but exact (plan P0 sur le programme de règles, `but` puis `paliers`). D qui échoue = bug.
Pour A et B, le plan est joué dans le vrai jeu et la théorie est comparée à chaque image (rejeu recalé) : 1re divergence.
Usage : uv run python experiments/instrument/diag4.py [K=40] [graine=0]  →  experiments/instrument/raw/diag4.json"""
import copy
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
os.environ.setdefault("CHRYS_AMODAL", "1")

from arcengine.enums import GameAction, GameState

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import buts_candidats, induire
from chrysalide.arc3.logique.jeux import environnement
from chrysalide.arc3.logique.plan import planifier
from chrysalide.arc3.logique.theorie import Theorie, rejeu
from chrysalide.arc3.moteur import MAX_BUTS_SUPPOSES, ORDRE_BUTS, _clics_offerts

PUBLICS = RACINE / "experiments/arc3/environment_files"
SELECTION = [("ft09", 1), ("tn36", 1), ("re86", 1), ("sp80", 1), ("ls20", 1), ("tr87", 1)]
LIMITE_PLAN, LIMITE_REEL, LIMITE_S = 50000, 3000, 120


def pas_reel(env, a):
    """a = 1..5 ou ('clic', x, y) en pixels → image (FrameData)."""
    if isinstance(a, tuple):
        return env.step(GameAction.ACTION6, data={"x": int(a[1]), "y": int(a[2])})
    return env.step(GameAction.from_id(a))


def amorce(gid, k, graine):
    """K coups au hasard depuis RESET, arrêtés avant toute fin de niveau ou mort (rejoués sur une copie d'essai)."""
    rnd, env = random.Random(graine), environnement(gid, PUBLICS)
    f = env.reset()
    grilles, acts, essais = [np.asarray(f.frame[-1])], [], 0
    while len(acts) < k:
        ids = sorted(set(f.available_actions or [1, 2, 3, 4]) - {7})
        a = rnd.choice(ids)
        if a == 6:
            g = grilles[-1]
            fond = np.bincount(g.ravel()).argmax()
            ys, xs = np.nonzero(g != fond)
            i = rnd.randrange(len(ys)) if len(ys) else 0
            a = ("clic", int(xs[i]) if len(xs) else 32, int(ys[i]) if len(ys) else 32)
        essai = copy.deepcopy(env)
        f2 = pas_reel(essai, a)
        essais += 1
        if essais > 50 * k:
            break  # garde-fou : presque tous les coups finissent le niveau ou la vie
        if f2.state in (GameState.WIN, GameState.GAME_OVER) or f2.levels_completed > 0:
            continue  # coup qui finirait le niveau ou la vie : on en tire un autre (l'amorce reste dans le niveau 1)
        env, f = essai, f2
        grilles.append(np.asarray(f.frame[-1]))
        acts.append(a)
        if len(grilles) > 4 * k:
            break
    return grilles, acts


def plan_D(gid):
    """Plan P0 (règles exactes, but exact) capturé au rejeu de plafonds.p0 ; coups au format (num, ligne, colonne)."""
    import plafonds
    pris, orig = [], plafonds.jouer
    plafonds.jouer = lambda env, c: (pris.append(c), orig(env, c))[1]
    try:
        for rech in ("but", "paliers"):
            pris.clear()
            r = plafonds.p0(gid, 1, 1000000, 600, rech)
            if r.get("gagne"):
                return list(pris), rech, r
    finally:
        plafonds.jouer = orig
    return None, None, r


def vers_c(c):
    return ("clic", int(c[2]), int(c[1])) if c[0] == 6 else int(c[0])


def jouer_plan(gid, plan_c, tr0, th=None):
    """Joue un plan (actions de C ; clics en CASES de tr0) dans le vrai jeu depuis RESET. → résultat + 1re divergence."""
    env = environnement(gid, PUBLICS)
    f = env.reset()
    grilles, acts, gagne, mort = [np.asarray(f.frame[-1])], [], False, False
    for a in plan_c:
        ap = ("clic", tr0.ox + a[1] * tr0.s + tr0.s // 2, tr0.oy + a[2] * tr0.s + tr0.s // 2) if isinstance(a, tuple) else a
        f = pas_reel(env, ap)
        if f.levels_completed > 0 or f.state == GameState.WIN:
            gagne = True
            break
        if f.state == GameState.GAME_OVER:
            mort = True
            break
        grilles.append(np.asarray(f.frame[-1]))
        acts.append(ap)
    r = {"plan": len(plan_c), "joues": len(acts) + (gagne or mort), "gagne": gagne, "mort": mort}
    if th is not None and acts:
        tr = Trajectoire([g.tolist() for g in grilles], acts, ech=(tr0.s, tr0.ox, tr0.oy))
        ok, n, premier = rejeu(th, tr, libre=False)
        r.update(predits_justes=ok, predits=n, premiere_divergence=premier)
        if premier is not None:
            monde, _ = th.pas(tr.etats[premier], tr.actions[premier], tr.taille)
            rd, vu = np.asarray(th.rendu(monde, tr.taille, tr.fond)), np.asarray(tr.cases[premier + 1])
            if rd.shape == vu.shape:
                r["cases_fausses"] = [[int(y), int(x), int(rd[y, x]), int(vu[y, x])]
                                      for y, x in zip(*np.nonzero(rd != vu), strict=True)][:12]
    return r


def actions_th(th, tr):
    vues = sorted({a for a in tr.actions if not isinstance(a, tuple)} - {7})
    return vues + (_clics_offerts(th, tr) if th.motif else [])


def candidats(th, tr):
    couleurs = {o[0] for e in tr.etats for o in e}
    cs = [x for x in buts_candidats(th, couleurs) if not any(Theorie._vrai(x, e) for e in tr.etats)]
    cs.sort(key=lambda x: ORDRE_BUTS.get(x[0], 9))
    return cs[:MAX_BUTS_SUPPOSES]


def config_A(th, tr):
    """But inféré comme MoteurC : but induit s'il existe, sinon le 1er but supposé planifiable."""
    if th.but is not None:
        plan, mondes = planifier(th, tr.etats[0], tr.taille, actions_th(th, tr), limite=LIMITE_PLAN)
        return plan, {"but": str(th.but), "source_but": "induit", "mondes": mondes}
    t0 = time.time()
    for x in candidats(th, tr):
        if time.time() - t0 > 2 * LIMITE_S:
            return None, {"but": None, "raison": "budget des buts supposés épuisé"}
        tb = th.pour_but(x)
        plan, mondes = planifier(tb, tr.etats[0], tr.taille, actions_th(tb, tr), limite=LIMITE_PLAN)
        if plan:
            return plan, {"but": str(x), "source_but": "supposé", "mondes": mondes, "theorie": tb}
    return None, {"but": None, "raison": "aucun but planifiable"}


def config_C(gid, th, tr):
    """Vrai jeu copié comme simulateur ; but = 1er candidat de A atteint par largeur (états dédoublonnés par image)."""
    cs = ([th.but] if th.but is not None else []) + candidats(th, tr)
    env0 = environnement(gid, PUBLICS)
    f0 = env0.reset()
    acts = sorted(set(f0.available_actions or [1, 2, 3, 4]) - {6, 7})
    if 6 in (f0.available_actions or []):
        import plafonds
        acts += [("clic", c[2], c[1]) for c in plafonds.clics(f0.frame[-1])]
    t0 = time.time()
    for x in cs:
        file, vus, n = [(env0, [])], {np.asarray(f0.frame[-1]).tobytes()}, 0
        while file and n < LIMITE_REEL and time.time() - t0 < LIMITE_S:
            env, chemin = file.pop(0)
            for a in acts:
                if time.time() - t0 > LIMITE_S:
                    break
                e2 = copy.deepcopy(env)
                f = pas_reel(e2, a)
                n += 1
                if f.state == GameState.GAME_OVER:
                    continue
                if f.levels_completed > 0 or f.state == GameState.WIN:
                    return {"but": str(x), "gagne": True, "plan": len(chemin) + 1, "noeuds": n,
                            "note": "vraie victoire atteinte pendant la recherche du but supposé"}
                g = np.asarray(f.frame[-1])
                k = g.tobytes()
                if k in vus:
                    continue
                vus.add(k)
                etat = Trajectoire([g.tolist()], [], ech=(tr.s, tr.ox, tr.oy)).etats[0]
                if Theorie._vrai(x, etat):
                    return {"but": str(x), "gagne": False, "plan": len(chemin) + 1, "noeuds": n,
                            "raison": "but supposé atteint, niveau non gagné"}
                file.append((e2, [*chemin, a]))
    return {"but": None, "gagne": False, "raison": "aucun candidat atteint (budget)" if cs else "aucun candidat",
            "candidats": len(cs)}


def diag(gid, k, graine):
    t0 = time.time()
    grilles, acts = amorce(gid, k, graine)
    tr = Trajectoire([g.tolist() for g in grilles], acts)
    th, _ = induire([(tr, None, None)], limite_s=LIMITE_S)
    ok, n, _ = rejeu(th, tr, libre=False)
    out = {"jeu": gid, "amorce": len(acts), "rejeu_amorce": [ok, n], "theorie": th.texte()[:600]}
    # D : règles exactes + but exact
    pd, rech, rd = plan_D(gid)
    out["D"] = {"gagne": pd is not None, "recherche": rech, "plan": len(pd) if pd else None,
                "raison": None if pd else rd.get("raison")}
    # A : induites + but inféré
    plan, info = config_A(th, tr)
    tha = info.pop("theorie", th)
    out["A"] = {**info, **(jouer_plan(gid, plan, tr, tha) if plan else {"gagne": False, "raison": info.get("raison")})}
    # B : induites + but « exact » = but induit par C avec la démonstration gagnante de D en plus
    if pd:
        env = environnement(gid, PUBLICS)
        f = env.reset()
        gd, ad = [f.frame[-1]], []
        for c in pd[:-1]:
            f = pas_reel(env, vers_c(c))
            gd.append(f.frame[-1])
            ad.append(vers_c(c))
        trd = Trajectoire([np.asarray(g).tolist() for g in gd], ad, ech=(tr.s, tr.ox, tr.oy))
        thd, _ = induire([(tr, None, None), (trd, None, vers_c(pd[-1]), "niveau")], limite_s=LIMITE_S)
        if thd.but is None:
            out["B"] = {"gagne": False, "raison": "but exact inexprimable dans le langage de C (rien induit)"}
        else:
            thb = th.pour_but(thd.but)
            plan, mondes = planifier(thb, tr.etats[0], tr.taille, actions_th(thb, tr), limite=LIMITE_PLAN)
            out["B"] = {"but": str(thd.but), "mondes": mondes,
                        **(jouer_plan(gid, plan, tr, thb) if plan else {"gagne": False, "raison": "pas de plan"})}
    else:
        out["B"] = {"gagne": False, "raison": "pas de démonstration (D a échoué)"}
    # C : exactes (vrai jeu) + but inféré
    out["C"] = config_C(gid, th, tr)
    # CW-230 B : état perçu + dynamique exacte + but exact (perception jugée sprite par sprite sur le chemin gagnant de D)
    try:
        out["Bp"] = config_Bp(gid, pd, (tr.s, tr.ox, tr.oy))
    except Exception as e:  # noqa: BLE001 — correspondance impossible = problème d'interface, noté comme tel
        out["Bp"] = {"gagne": False, "classe": "adaptateur", "raison": f"{type(e).__name__}: {e}"[:160]}
    out["secondes"] = round(time.time() - t0, 1)
    return out


def main():
    import faulthandler
    faulthandler.dump_traceback_later(900, repeat=True)  # pile toutes les 15 min dans le journal (étape lente)
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    graine = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    jeux = sys.argv[3].split(",") if len(sys.argv) > 3 else [g for g, _ in SELECTION]
    sortie = RACINE / "experiments/instrument/raw" / f"diag4_k{k}_g{graine}{os.environ.get('DIAG_SUFFIXE', '')}.json"
    if os.environ.get("DIAG_SORTIE"):  # banc de nuit : sortie imposée
        sortie = Path(os.environ["DIAG_SORTIE"])
    sortie.parent.mkdir(parents=True, exist_ok=True)
    res = json.loads(sortie.read_text()) if sortie.exists() else {}
    for gid in jeux:
        try:
            res[gid] = diag(gid, k, graine)
        except Exception as e:  # noqa: BLE001 — échec compté
            import traceback
            res[gid] = {"jeu": gid, "plantage": f"{type(e).__name__}: {e}", "pile": traceback.format_exc()[-800:]}
        r = res[gid]
        print(gid, {c: (r.get(c) or {}).get("gagne") for c in "ABCD"}, r.get("plantage", ""), flush=True)
        sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))



def config_Bp(gid, pd, ech):
    """CW-230 B = état PERÇU + dynamique exacte + but exact. La dynamique exacte (le vrai jeu) joue le plan gagnant de D ; à
    chaque état, chaque sprite visible du moteur est rendu SEUL puis perçu : il est « perçu juste » si ses objets sont tous
    dans la perception de l'image entière. B gagne ssi la perception est juste sur tout le chemin ; sinon 1er instant fautif
    + classe : « identité » (objet absent ou fondu dans un autre : occultation, fusion), « position » (même objet ailleurs)."""
    import copy as cp

    from mesure_exhaustivite import _resync
    if not pd:
        return {"gagne": False, "raison": "pas de plan exact (D)"}
    env = environnement(gid, PUBLICS)
    f = env.reset()
    tr0 = Trajectoire([np.asarray(f.frame[-1]).tolist()], [], ech=ech)
    for t in range(len(pd)):
        g = np.asarray(f.frame[-1]).tolist()
        sc = _resync(env, None, False)
        vus, plein = set(tr0.etat(g)), np.asarray(sc.image())
        for s in [s for s in sc.sprites if s.get("visible", True)]:
            seul = cp.copy(sc)
            seul.sprites = [s]
            im = np.asarray(seul.image())
            visible = (im != sc.fond) & (im == plein)  # seulement les pixels du sprite visibles dans l'image entière
            if not visible.any():
                continue  # sprite entièrement caché : rien à percevoir
            objs = set(tr0.etat(np.where(visible, im, sc.fond).tolist()))
            if objs - vus:
                manque = sorted(objs - vus)[:3]
                cls = "position" if any((o[0], o[1]) in {(v[0], v[1]) for v in vus} for o in objs - vus) else "identité"
                return {"gagne": False, "premier_instant": t, "classe": cls, "sprite": str(s.get("nom")),
                        "objets_manquants": [str(o)[:80] for o in manque]}
        f = pas_reel(env, vers_c(pd[t]))
    return {"gagne": True, "pas": len(pd)}


if __name__ == "__main__":
    main()
