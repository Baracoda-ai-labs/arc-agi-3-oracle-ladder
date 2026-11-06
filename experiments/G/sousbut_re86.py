"""[G] CW-354.4, sous-but : re86 N5, but `marques` (1er candidat : 8 marques à couvrir par des pièces). Sous-buts
cumulés (essai doublé après un passage sans succès) : à chaque étape, but = marques déjà couvertes + UNE marque de plus (essayées dans l'ordre, T_ESSAI s chacune
avec `macro_g` gel 2) ; le plan trouvé est rejoué dans le programme, l'étape suivante part de là. Budget TOTAL S s
(temps égal à V0 et `macro_g` sur le but entier, `banc_re86.py`). Plans non rejoués dans le vrai jeu ici.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/sousbut_re86.py [S=300] [T_ESSAI=20] → lignes JSON"""
import json
import os
import pickle
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
D = pickle.loads((RACINE / "experiments/T3.0/dossiers_g/re86_n5.pkl").read_bytes())
os.environ.update(D["drapeaux"])
sys.path[:0] = [str(RACINE / "experiments/G"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
if os.environ.get("G_BUT_MARQUES", "1") == "1":  # correctif local du but `marques` (but_marques.py)
    __import__("but_marques").installer()
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner


def main():
    S = float(sys.argv[1]) if len(sys.argv) > 1 else 300
    T_ESSAI = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    from banc_p0 import _init
    _init()
    import macro_g
    th = D["theorie"]
    but = next(b for b in D["buts"] if b[0] == "marques")
    marques = [(c, z) for c, cs in but[1] for z in cs]
    s = Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])
    th.but = but
    p = ProgrammeCompile(exporter(th, D["taille"])[0])
    etat = p.etat
    faites, plan, t0 = [], [], time.process_time()
    while len(faites) < len(marques) and time.process_time() - t0 < S:
        trouve = False
        for m in marques:
            if m in faites or time.process_time() - t0 >= S:
                continue
            groupes = {}
            for c, z in [*faites, m]:
                groupes.setdefault(c, []).append(z)
            th.but = ("marques", tuple((c, tuple(zs)) for c, zs in groupes.items()), but[2])
            prog, non = exporter(th, D["taille"])
            if non:
                print(json.dumps({"non_exportes": non}), flush=True)
                return
            s2, e2 = cloner(s, etat)
            r = macro_g.chercher("re86", D["niveau"], 10 ** 6, min(T_ESSAI, S - (time.process_time() - t0)), texte=prog,
                                 scene=s2, etat=e2, actions=[1, 2, 3, 4, 5], verifier=False)
            if not r.get("coups"):
                continue
            q = ProgrammeCompile(prog)
            q.etat = e2
            s3, e3 = cloner(s, etat)
            q.etat = e3
            for a in r["coups"]:
                q.step(s3, (a, None, None))
            s3.issue = None  # le sous-but atteint a posé « niveau » : la scène suivante repart sans issue
            s, etat = s3, q.etat
            faites.append(m)
            plan += r["coups"]
            print(json.dumps({"marque": str(m), "coups": len(r["coups"]), "cumul": len(plan), "faites": len(faites),
                              "cpu": round(time.process_time() - t0, 1)}), flush=True)
            trouve = True
            break
        if not trouve:  # aucun sous-but en T_ESSAI : on double l'essai (budget total inchangé), arrêt si plus de temps
            T_ESSAI *= 2
    print(json.dumps({"resultat": "plan" if len(faites) == len(marques) else "partiel", "faites": len(faites),
                      "sur": len(marques), "coups": plan, "cpu": round(time.process_time() - t0, 1)}), flush=True)


if __name__ == "__main__":
    main()
