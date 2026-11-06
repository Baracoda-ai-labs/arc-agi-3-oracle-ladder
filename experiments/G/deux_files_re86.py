"""[G] CW-357 (impasse « recherche ») : DEUX FILES à temps égal sur re86 N5 (dossier de C au HEAD, but `marques`
exporté par C). Budget total S : moitié pour `macro_g` (gel 2) sur le but entier, moitié pour la chaîne de sous-buts
(marques cumulées une à une). Sous-buts NON gourmands : quand aucune marque restante n'est atteinte en T_ESSAI, on
repart du DÉBUT avec les marques résistantes placées en tête de l'ordre (au plus R redémarrages) ; essai doublé si un
ordre déjà tenté revient. Le 1er plan trouvé (file 1 ou 2) est rejoué coup par coup dans le VRAI jeu (préfixe de
`plafonds.env_au_niveau`), arrêt au franchissement. Témoin à temps égal : `macro_g` seul sur S entier (`banc_re86.py`).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/deux_files_re86.py [S=300] [T_ESSAI=20] → lignes JSON"""
import json
import os
import pickle
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CAS = os.environ.get("G_CAS", "re86_n5")  # dossier de C (ex. re86_n5_peint)
D = pickle.loads((RACINE / f"experiments/T3.0/dossiers_g/{CAS}.pkl").read_bytes())
os.environ.update(D["drapeaux"])
sys.path[:0] = [str(RACINE / "experiments/G"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner

T = time.process_time


def scene0():
    return Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])


def chercher(macro_g, prog, s, e, sec):
    s2, e2 = cloner(s, e)
    return macro_g.chercher("re86", D["niveau"], 10 ** 6, sec, texte=prog, scene=s2, etat=e2, actions=[1, 2, 3, 4, 5],
                            verifier=False)


def sous_buts(macro_g, th, but, budget, t_essai, redemarrages=6):
    marques = [(c, z) for c, cs in but[1] for z in cs]
    t0, ordre, essai, vus, journal = T(), list(marques), t_essai, set(), []
    for _r in range(redemarrages + 1):
        s, faites, plan = scene0(), [], []
        th.but = but
        etat = ProgrammeCompile(exporter(th, D["taille"])[0]).etat
        resistantes = []
        while len(faites) < len(marques) and T() - t0 < budget:
            trouve = False
            for m in ordre:
                if m in faites or T() - t0 >= budget:
                    continue
                groupes = {}
                for c, z in [*faites, m]:
                    groupes.setdefault(c, []).append(z)
                th.but = ("marques", tuple((c, tuple(zs)) for c, zs in groupes.items()), but[2])
                prog, non = exporter(th, D["taille"])
                assert not non, non
                r = chercher(macro_g, prog, s, etat, min(essai, budget - (T() - t0)))
                if not r.get("coups"):
                    resistantes.append(m)
                    continue
                q = ProgrammeCompile(prog)
                s3, q.etat = cloner(s, etat)
                for a in r["coups"]:
                    q.step(s3, (a, None, None))
                s3.issue = None
                s, etat = s3, q.etat
                faites.append(m)
                plan += r["coups"]
                trouve = True
                break
            if not trouve:
                break
        journal.append({"ordre": [str(m) for m in ordre[:3]], "faites": len(faites), "coups": len(plan),
                        "cpu": round(T() - t0, 1)})
        if len(faites) == len(marques):
            return plan, journal
        if T() - t0 >= budget:
            break
        # redémarrage : marques résistantes en tête, puis l'ordre de réussite, puis le reste
        nouvel = list(dict.fromkeys([*resistantes, *faites, *ordre]))
        if tuple(nouvel) in vus:
            essai *= 2
        vus.add(tuple(nouvel))
        ordre = nouvel
    return None, journal


def rejeu(plan):
    r = subprocess.run([sys.executable, str(RACINE / "experiments/G/rejeu_re86.py"), str(D["niveau"]), ",".join(plan)],
                       capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(RACINE)}, check=False)
    lignes = [x for x in r.stdout.splitlines() if x.startswith("{")]
    return json.loads(lignes[-1]) if lignes else {"erreur": r.stderr[-300:]}


def main():
    S = float(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_essai = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    from banc_p0 import _init
    _init()
    import macro_g
    th = D["theorie"]
    but = next(b for b in D["buts"] if b[0] == "marques")
    th.but = but
    prog, non = exporter(th, D["taille"])
    assert not non, non
    t0 = T()
    r1 = chercher(macro_g, prog, scene0(), ProgrammeCompile(prog).etat, S / 2)
    f1 = {"plan": len(r1["coups"]) if r1.get("coups") else None, "arret": r1.get("arret"), "cpu": round(T() - t0, 1)}
    print(json.dumps({"file": "but entier", **f1}), flush=True)
    plan = r1.get("coups")
    t1 = T()
    p2, journal = sous_buts(macro_g, th, but, S - (t1 - t0), t_essai)
    print(json.dumps({"file": "sous-buts", "plan": len(p2) if p2 else None, "cpu": round(T() - t1, 1),
                      "journal": journal}), flush=True)
    plan = plan or p2
    if plan:
        print(json.dumps({"rejeu_reel": rejeu(plan), "plan": plan}), flush=True)


if __name__ == "__main__":
    main()
