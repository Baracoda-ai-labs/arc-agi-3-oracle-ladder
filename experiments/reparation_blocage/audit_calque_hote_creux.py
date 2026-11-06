"""Rejeu prédictif gelé de la correction générique ; aucun SDK."""
import json,copy,cloudpickle
from pathlib import Path
import numpy as np
from chaine_agent_integree import canon,lots
from chaine_coherente import Chaine
from transfert_modele_c import reaffecter
from revision_perception_selection import reviser,porteur_boite
R=Path(__file__).resolve().parent
z=np.load(R/'runs/session_re86_transfert_c2/N2/partie.npz')
rows=json.loads((R/'runs/session_re86_transfert_c2/N2/partie.json').read_text())['rows']
s=cloudpickle.loads((R/'runs/session_re86_buts_conserves1/modele_gagnant_local.pkl').read_bytes())
c,_=reaffecter(s,z['images'][0],[canon(i) for i in (1,2,3,4,5)])
c,diag=reviser(c,z['images'][0],z['images'][1],canon(5),z['film_1'])
_,(pc,sc)=c.rejouer()
res=[]
for i in range(1,len(rows)):
    pc.step(sc,canon(rows[i]['action']))
    pred=c.perception.rendu(sc);real=c.perception.vue(z['images'][i+1]);xy=np.argwhere(pred!=real)
    res.append(dict(coup=i+1,pixels_ecart=len(xy),pixels=[[int(y),int(x),int(pred[y,x]),int(real[y,x])] for y,x in xy][:20]))
    if len(xy):break
# Vérifier les préfixes complets sans réutiliser un programme compilé copié.
checks=[]
for n in range(1,min(7,len(rows))):
    v=copy.deepcopy(c.perception)
    nc=Chaine(v,copy.deepcopy(c.programme),z['images'][:n+1].tolist(),lots([r['action'] for r in rows[:n]]),c.actions)
    co,state=nc.rejouer();checks.append(dict(prefixe=n,controle=co))
d=dict(calibration=1,predictions=res,prefixes=checks,sdk=0)
(R/'AUDIT_CALQUE_HOTE_CREUX.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d))
