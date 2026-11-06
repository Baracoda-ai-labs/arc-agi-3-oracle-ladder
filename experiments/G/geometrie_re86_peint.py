"""[G] re86 N5 (dossier `re86_n5_peint`, meilleures couvertures partielles) : couverture GÉOMÉTRIQUE des marques du but `marques` (dossier de C) par les pièces, translations au pas 3
(celui du porteur de la théorie), pièces dans la grille. Les mobiles (12, 283, 286, lus dans la théorie : sélection
par SPACE) seuls ne couvrent jamais les 8 marques. Usage : PYTHONPATH=. .venv/bin/python experiments/G/geometrie_re86.py"""
import pickle, numpy as np, itertools
D=pickle.load(open("/Users/ts/models/chrysalide3/experiments/T3.0/dossiers_g/re86_n5_peint.pkl","rb"))
marq=[z for c,cs in next(b for b in D["buts"] if b[0]=="marques")[1] for z in cs]
pieces=[]
for o in D["sprites_depart"]:
    px=np.asarray(o["pixels"]); ys,xs=np.nonzero(px>=0); c=int(px[px>=0].max())
    if len(xs)>1 and c<512 and px.shape[0]*px.shape[1]<64*64/4 and len(xs)>8:
        pieces.append((c,o["x"],o["y"],px.shape,{(int(x),int(y)) for y,x in zip(ys,xs)}))
print("pièces", [(c,x,y,sh,len(cs)) for c,x,y,sh,cs in pieces])
best=[]
for c,x0,y0,sh,cs in pieces:
    opts={}
    for dx in range(-66,67,3):
        for dy in range(-66,67,3):
            x,y=x0+dx,y0+dy
            if x<0 or y<0 or x+sh[1]>64 or y+sh[0]>64: continue
            cov=frozenset(m for m in marq if (m[0]-x,m[1]-y) in cs)
            if cov: opts[cov]=(x,y)
    mx=max(opts,key=len); print(c, "max marques par position", len(mx), "positions distinctes", len(opts))
    best.append((c,opts))
best=[b for b in best if b[0] in (12,283,286)]
import itertools as it
res=[]
for sel in it.product(*[list(o.items()) for _,o in best]):
    u=frozenset().union(*[x[0] for x in sel]); res.append((len(u), [ (c, x[1]) for (c,_),x in zip(best,sel)], sorted(set(marq)-u)))
res.sort(key=lambda t:-t[0]); m=res[0][0]
print("meilleure couverture", m, "/", len(marq))
from collections import Counter
print("marques manquantes dans les meilleures:", Counter(str(z) for r in res if r[0]==m for z in r[2]))
for r in res[:4]: print(r)
