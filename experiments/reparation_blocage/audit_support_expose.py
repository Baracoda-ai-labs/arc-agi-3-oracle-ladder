"""Préparation hors SDK d'un clic sur masque observé non occulté."""
import json
from pathlib import Path
import numpy as np
from support_planificateur_audit import preparer

R=Path(__file__).parent/'runs'
m,h,cs,z,j,rule=preparer()
im=z['images'][6];cx,cy=m.position(im)
ys,xs=np.nonzero(np.isin(im,list(m.palette)))
# Même ligne que le centre ; hors boîte de la silhouette et dans le delta acquis.
choices=sorted((abs(x-cx),x,y) for x,y in rule['pixels_xy'] if y==cy and im[y,x]==m.sol and (x<xs.min() or x>xs.max()))
if not choices: raise ValueError('Aucun pixel expose sur ligne du controle')
_,x,y=choices[0];action=['clic',x,y];duplicates=[];count=0
for d in R.iterdir():
    if not d.is_dir() or not ('bp35' in d.name.lower() or d.name.startswith(('route_phase_N3','contact_N3','horloges_N3','annulation_N3','refermeture_N3','support_occupe'))):continue
    for p in d.glob('N*/partie.json'):
        if not p.with_suffix('.npz').exists():continue
        jj=json.loads(p.read_text());zz=np.load(p.with_suffix('.npz'))
        for i,a in enumerate(jj['actions']):
            count+=1
            if a==action and np.array_equal(zz['images'][i],im):duplicates.append([str(p),i])
print(json.dumps({'action':action,'centre_controle':[cx,cy],'boite_palette':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'appartient_delta_observe':True,'pixel_sol_visible':True,'actions_indexees':count,'doublons_exacts':duplicates,'limite':'hitbox inconnue; pixel expose ne garantit pas cible clickable; index cible non exhaustif','sdk':0}))
