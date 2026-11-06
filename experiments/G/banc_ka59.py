"""[G] CW-361 / CCM-269-C : ka59 N4 jusqu'au plan gagnant dans le vrai jeu. Dossier de C `dossiers_g/<cas>.pkl`
(théorie sous CREUX + SELECTION_CLIC, rejeu 60/60, but `emboite` à 4 cibles), exporté ; `macro_g` (gel 2) depuis le
départ du niveau, flèches + clics (clics candidats = `plafonds.clics` sur l'image réelle du début du niveau, préfixe
`plafonds.env_au_niveau`) ; plan rejoué coup par coup dans le VRAI jeu, arrêt au franchissement ou à la fin.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_ka59.py [S=300] [cas=ka59_n4_creux] → lignes JSON"""
import json
import os
import pickle
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
S = float(sys.argv[1]) if len(sys.argv) > 1 else 300
CAS = sys.argv[2] if len(sys.argv) > 2 else "ka59_n4_creux"
D = pickle.loads((RACINE / f"experiments/T3.0/dossiers_g/{CAS}.pkl").read_bytes())
os.environ.update(D["drapeaux"])
sys.path[:0] = [str(RACINE / "experiments/G"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
import numpy as np

from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile

CODE = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5}


def coup_reel(c):
    if c in CODE:
        return (CODE[c], None, None)
    m = re.match(r"CLICK\D*(\d+)\D+(\d+)", c)
    return (6, int(m.group(1)), int(m.group(2)))


def sous_buts(macro_g, th, s0, img, budget, t_essai=60):
    """`emboite` cible par cible, cumulé (but = cibles déjà faites + une) ; tous les ordres (≤ 3! = 6), essai doublé
    après un passage sans succès ; macro_g (clics recalculés sur la scène) sur chaque sous-but. → dict (coups ou None)."""
    import itertools

    from chrysalide.arc3.sim_rapide import cloner
    but = th.but
    t0, journal = time.process_time(), []
    for ordre in itertools.permutations(but[1]):
        s, etat, plan, faites = s0, None, [], []
        th.but = but
        etat = ProgrammeCompile(exporter(th, D["taille"])[0]).etat
        for cible in ordre:
            reste = budget - (time.process_time() - t0)
            if reste <= 0:
                break
            th.but = (but[0], (*faites, cible), *but[2:])  # paires imposées (but[3]) gardées
            prog = exporter(th, D["taille"])[0]
            s2, e2 = cloner(s, etat)
            r = macro_g.chercher(CAS.split("_")[0], D["niveau"], 10 ** 6, min(t_essai, reste), texte=prog, scene=s2,
                                 etat=e2, actions=[1, 2, 3, 4, 6], image=img, verifier=False, clics_scene=os.environ.get("G_CLICS", "pilotes") if os.environ.get("G_CLICS", "pilotes") != "tous" else True)
            if not r.get("coups"):
                break
            q = ProgrammeCompile(prog)
            s3, q.etat = cloner(s, etat)
            for c in r["coups"]:
                q.step(s3, ("CLICK", *map(int, re.findall(r"\d+", c))) if c.startswith("CLICK") else (c, None, None))
            s3.issue = None
            s, etat = s3, q.etat
            faites.append(cible)
            plan += r["coups"]
        journal.append({"ordre": [list(c) for c in ordre], "faites": len(faites), "coups": len(plan),
                        "cpu": round(time.process_time() - t0, 1)})
        th.but = but
        if len(faites) == len(but[1]):
            return {"coups": plan, "plan": len(plan), "journal": journal}
        if time.process_time() - t0 >= budget:
            break
    return {"coups": None, "plan": None, "journal": journal}


def main():
    from banc_p0 import _init
    _init()
    import macro_g
    import plafonds as pf
    gid = CAS.split("_")[0]
    th = D["theorie"]
    th.but = next(b for b in D["buts"] if b[0] == "emboite")
    if os.environ.get("G_BUT"):  # variante de but pour diagnostic (ex. cibles et pièces restreintes), annoncée au rapport
        th.but = eval(os.environ["G_BUT"])
    prog, non = exporter(th, D["taille"])
    env, f0 = pf.env_au_niveau(gid, D["niveau"])
    img = np.asarray(f0.frame[-1])
    ligne = {"cas": CAS, "but": str(th.but), "non_exportes": non, "niveaux_avant": f0.levels_completed,
             "clics_candidats": len(pf.clics(img))}
    print(json.dumps(ligne, ensure_ascii=False), flush=True)
    if non:
        return
    s = Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])
    t0 = time.process_time()
    if os.environ.get("G_SOUSBUTS") == "1":  # cibles une à une, cumulées, chaque ordre essayé (budget total S)
        r = sous_buts(macro_g, th, s, img, S, float(os.environ.get("G_T_ESSAI", "60")))
        print(json.dumps({"recherche": "sous-buts", **r}, ensure_ascii=False), flush=True)
        coups = r.get("coups")
    else:
        r = macro_g.chercher(gid, D["niveau"], 10 ** 6, S, texte=prog, scene=s, etat=ProgrammeCompile(prog).etat,
                             actions=[1, 2, 3, 4, 6], image=img, verifier=False,
                             clics_scene=os.environ.get("G_CLICS_SCENE") == "1")
        print(json.dumps({"recherche": "macro_g", **{x: r.get(x) for x in ("arret", "plan", "etats_hauts", "coups")},
                          "cpu": round(time.process_time() - t0, 1)}, ensure_ascii=False), flush=True)
        coups = r.get("coups")
    if not coups:
        return
    f, joues = f0, 0
    for c in coups:
        f = pf.jouer(env, coup_reel(c))
        joues += 1
        if f.levels_completed > f0.levels_completed or f.state.name in ("WIN", "GAME_OVER"):
            break
    print(json.dumps({"rejeu_reel": {"coups": joues, "sur": len(coups), "etat": f.state.name,
                                     "franchi": f.levels_completed > f0.levels_completed or f.state.name == "WIN"}}),
          flush=True)


if __name__ == "__main__":
    main()
