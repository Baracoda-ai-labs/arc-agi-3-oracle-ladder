"""[G] CW-354.4 : re86 N5 (dossier de C, `experiments/T3.0/dossiers_g/re86_n5.pkl`, théorie induite sur la trace de B,
export entier, 16 buts candidats du moteur). Par but : `macro_g` (gel 2) à 20 s (budget de E, CCM-051-E) puis à S s, et
V0 = largeur exacte sur le même programme (`guidage.meilleur_dabord`, h = 0) à S s. Plans non rejoués ici (mesure de
la recherche ; rejeu coup par coup dans le vrai jeu ensuite, arrêt à la 1re divergence, CCM-251-C).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/banc_re86.py <i_but,…> [S=300] [cas=re86_n5] → lignes JSON"""
import json
import os
import pickle
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CAS = sys.argv[3] if len(sys.argv) > 3 else "re86_n5"
D = pickle.loads((RACINE / f"experiments/T3.0/dossiers_g/{CAS}.pkl").read_bytes())
os.environ.update(D["drapeaux"])  # drapeaux de C, posés avant tout import du moteur
sys.path[:0] = [str(RACINE / "experiments/G"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
from guidage import meilleur_dabord

if os.environ.get("G_BUT_MARQUES", "1") == "1":  # correctif local du but `marques` (but_marques.py)
    __import__("but_marques").installer()
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile

NOMS = ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")


def main():
    idx = [int(x) for x in sys.argv[1].split(",")]
    sec = float(sys.argv[2]) if len(sys.argv) > 2 else 300
    from banc_p0 import _init
    _init()
    import macro_g
    th = D["theorie"]
    for i in idx:
        b = D["buts"][i]
        th.but = b
        prog, non = exporter(th, D["taille"])
        ligne = {"cas": CAS, "i": i, "but": str(b), "non_exportes": non}
        if non:
            print(json.dumps(ligne, ensure_ascii=False), flush=True)
            continue

        def scene():
            return Scene((D["taille"][1], D["taille"][0]), D["fond"], D["fond"], [dict(o) for o in D["sprites_depart"]])
        for s_ in (20, sec):
            p = ProgrammeCompile(prog)
            r = macro_g.chercher(CAS[:4], D["niveau"], 10 ** 6, s_, texte=prog, scene=scene(), etat=p.etat,
                                 actions=[1, 2, 3, 4, 5], verifier=False)
            ligne[f"macro_{int(s_)}"] = {x: r.get(x) for x in ("arret", "plan", "etats_hauts", "cpu")} | \
                {"coups": r.get("coups")}
        p = ProgrammeCompile(prog)
        plan, inf = meilleur_dabord(prog, scene(), p.etat, [(a, None, None) for a in NOMS], lambda sc: 0, 10 ** 7, sec)
        ligne["v0"] = {"plan": None if plan is None else len(plan), "coups": plan, **inf}
        print(json.dumps(ligne, ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
