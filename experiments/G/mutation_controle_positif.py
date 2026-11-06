"""[G] CW-467.4 (b), CONTRÔLE POSITIF du test de mutation : `cloner` remplacé par une version qui PARTAGE l'état caché
entre branches (défaut injecté) ; le test doit échouer. Usage : PYTHONPATH=. .venv/bin/python experiments/G/mutation_controle_positif.py"""
import json
import os
import pickle
import sys

sys.path[:0]=["/Users/ts/models/chrysalide3","/Users/ts/models/chrysalide3/experiments/G"]
from pathlib import Path

import mutation_branches as M

import chrysalide.arc3.sim_rapide as SR

R=Path("/Users/ts/models/chrysalide3")
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.ontologie_exec import Scene

D=pickle.loads((R/"experiments/T3.0/dossiers_g/ka59_n4_creux.pkl").read_bytes()); os.environ.update(D["drapeaux"])
t=D["theorie"]; t.but=D["buts"][0]; pg,_=exporter(t,D["taille"])
s=Scene((D["taille"][1],D["taille"][0]),D["fond"],D["fond"],[dict(o) for o in D["sprites_depart"]])
acts=[(a,None,None) for a in ("UP","DOWN","LEFT","RIGHT")]+[("CLICK",32,30)]
vrai=SR.cloner
def faux(sc, e):  # défaut injecté : la scène est copiée mais l'état caché est PARTAGÉ entre branches
    s2,_=vrai(sc, e); return s2, e
SR.cloner=faux
print(json.dumps(M.programme("ka59 + état partagé (contrôle positif)", pg, s, None, acts), default=str))
