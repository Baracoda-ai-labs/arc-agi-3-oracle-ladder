"""[G] ka59 N4, expériences HORS LIGNE dans le vrai jeu (jeu public, CW-357 `Experience`) : pousser le jumeau (à droite,
en bas), puis plan « deux cadres ». Usage : PYTHONPATH=. .venv/bin/python experiments/G/experience_pousse_ka59.py"""
import sys, os, numpy as np
sys.path += ["/Users/ts/models/chrysalide3/experiments/T3.0","/Users/ts/models/chrysalide3/experiments/T3.1"]
os.chdir("/Users/ts/models/chrysalide3")
import plafonds as pf
from scipy import ndimage
def objs(g, cols=(14,11,5)):
    g=np.asarray(g); out=[]
    for c in cols:
        lab,n=ndimage.label(g==c)
        for i in range(1,n+1):
            ys,xs=np.nonzero(lab==i); out.append((c,int(xs.min()),int(ys.min())))
    return out
for seq in ([4,4,4,2,2,2], [2,4,4,4,4,4,2,2,2,2], [4,4,4,2,2,2,2,2]):
    env,f=pf.env_au_niveau("ka59",4); print("séquence", seq)
    for a in seq:
        f=pf.jouer(env,(a,None,None)); print("  ",{1:"U",2:"D",3:"L",4:"R"}[a], objs(f.frame[-1]), f.levels_completed, f.state.name)
print("=== plan complet")
env,f=pf.env_au_niveau("ka59",4)
plan=[(4,None,None)]*3+[(2,None,None)]+[(6,47,29)]+[(4,None,None)]*3+[(2,None,None)]*2+[(6,29,29)]+[(4,None,None)]*7
for a in plan:
    f=pf.jouer(env,a); print("  ",a, objs(f.frame[-1]), f.levels_completed, f.state.name)
    if f.levels_completed>3: print("NIVEAU FRANCHI"); break
